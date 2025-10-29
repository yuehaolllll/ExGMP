# In processing/rsca_model.py

import torch
import torch.nn as nn
import torch.nn.functional as F

# ---------------------------------------------------
# 模块一：SCConv
# ---------------------------------------------------
class SCConv(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, stride=1, padding=0, groups=1, bias=False):
        super(SCConv, self).__init__()
        self.half_in_channels = in_channels // 2
        self.half_out_channels = out_channels // 2
        self.avg_pool = nn.AdaptiveAvgPool1d(1)
        self.conv_k3 = nn.Conv1d(self.half_in_channels, self.half_out_channels, kernel_size, stride, padding,
                                 groups=groups, bias=bias)
        self.sigmoid = nn.Sigmoid()
        self.conv_k1 = nn.Conv1d(self.half_in_channels, self.half_out_channels, kernel_size, stride, padding,
                                 groups=groups, bias=bias)

    def forward(self, x):
        x1, x2 = torch.chunk(x, 2, dim=1)
        x1_down = self.avg_pool(x1)
        x1_up = F.interpolate(x1_down, size=x1.size()[2:], mode='linear', align_corners=False)
        attn = self.sigmoid(x1_up + x1)
        x1_w = x1 * attn
        y1 = self.conv_k3(x1_w)
        y2 = self.conv_k1(x2)
        return torch.cat((y1, y2), dim=1)

# -------------------------------------------------------
# 模块二：MSCA
# -------------------------------------------------------
class MSCA(nn.Module):
    def __init__(self, channels, reduction_ratio=16):
        super(MSCA, self).__init__()
        reduced_channels = channels // reduction_ratio
        self.global_branch = nn.Sequential(
            nn.AdaptiveAvgPool1d(1),
            nn.Conv1d(channels, reduced_channels, 1, bias=False),
            nn.BatchNorm1d(reduced_channels),
            nn.ReLU(inplace=True),
            nn.Conv1d(reduced_channels, channels, 1, bias=False)
        )
        self.local_branch = nn.Sequential(
            nn.Conv1d(channels, reduced_channels, 1, bias=False),
            nn.BatchNorm1d(reduced_channels),
            nn.ReLU(inplace=True),
            nn.Conv1d(reduced_channels, channels, 1, bias=False)
        )
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        g_w = self.global_branch(x)
        l_w = self.local_branch(x)
        attn = self.sigmoid(l_w + g_w)
        return x * attn

# -------------------------------------------------------------------
# 模块三：HRSC_Block
# -------------------------------------------------------------------
class HRSC_Block(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size=3, stride=1, scales=4, use_scconv=True):
        super(HRSC_Block, self).__init__()
        assert out_channels % scales == 0
        self.scales = scales
        self.width = out_channels // scales
        conv_type = SCConv if use_scconv else nn.Conv1d
        self.convs = nn.ModuleList([conv_type(in_channels, self.width, kernel_size, stride, padding=kernel_size // 2)])
        for _ in range(scales - 1):
            self.convs.append(conv_type(self.width, self.width, kernel_size, stride, padding=kernel_size // 2))
        self.shortcut = nn.Identity()
        if in_channels != out_channels:
            self.shortcut = nn.Conv1d(in_channels, out_channels, kernel_size=1, stride=stride, bias=False)
        self.bn = nn.BatchNorm1d(out_channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        shortcut = self.shortcut(x)
        outputs = []
        sp = self.convs[0](x)
        outputs.append(sp)
        for i in range(1, self.scales):
            sp = self.convs[i](sp)
            outputs.append(sp)
        out = torch.cat(outputs, dim=1)
        out += shortcut
        return self.relu(self.bn(out))

# -------------------------------------------------------------------
# 最终模型：RSCA 网络 (RSCA-Net)
# -------------------------------------------------------------------
class RSCA_Net(nn.Module):
    """
    完整的 RSCA 网络，用于EOG信号分类。
    """
    def __init__(self, in_channels, num_classes, scales=4):
        super(RSCA_Net, self).__init__()
        self.stem = nn.Sequential(
            nn.Conv1d(in_channels, 64, kernel_size=7, stride=2, padding=3, bias=False),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=3, stride=2, padding=1)
        )
        self.hrsc_block1 = HRSC_Block(64, 128, scales=scales)
        self.hrsc_block2 = HRSC_Block(128, 256, scales=scales)
        self.hrsc_block3 = HRSC_Block(256, 512, scales=scales)
        self.msca = MSCA(channels=512)
        self.avgpool = nn.AdaptiveAvgPool1d(1)
        self.fc = nn.Linear(512, num_classes)

    def forward(self, x):
        x = self.stem(x)
        x = self.hrsc_block1(x)
        x = self.hrsc_block2(x)
        x = self.hrsc_block3(x)
        x = self.msca(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.fc(x)
        return x