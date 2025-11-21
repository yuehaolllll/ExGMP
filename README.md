# ExG Monitor Platform

## 一、解耦与生产者-消费者模式
### 1. UI是数据的观察者，而不是数据的管理者.  
DataReceive/DataProcessor像流水线一样快速接收、处理数据，不关心用户在做什么  
### 2. 锁要快进快出.  
*不能在持有锁的代码块中做运算等消耗CPU，UI一旦卡顿会导致锁一直被占用，从而导致阻塞。故设计如下:*  
*DataProcessor: 仅做内存写入->立即释放*  
*TimeDomainWidget: 仅做numpy.copy() -> 立即释放 -> 锁外进行绘图坐标计算*  
*以此极大减少线程竞争，消除死锁或饿死现象.*
## 二、数据处理优化
### 1. 向量化与零拷贝  
*数据解析: 使用numpy.frombuffer + reshape + 位运算*
*数据存储: 使用numpy ring buffer*  
*CPU占有率大大下降，内存碎片化消失.*  
### 2. 优化滤波算法  
*标准的lfilter在高采样率（4000Hz或更高）低截止频率（0.5Hz）的情况下，会因精度问题导致数值发散.*  
*故全线切换为SOS（Second-Order Sections）级联结构.*  
## 