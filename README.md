# pigroom
####导语
>本项目志在构建一个类似于gitter的在线聊天室,使用websocket进行通信，服务端使用python进行架构。

####应用
借助于tornado异步请求非阻塞的特性：http://docs.pythontab.com/tornado/introduction-to-tornado/
消息队列暂定redis的发布订阅模式，使用插件https://github.com/leporo/tornado-redis
***
####第一个demo
ok，没有系统架构，没有分层，没有日志。。。什么都没有，就是个demo，23333
######试一试吧
打开[websocket测试工具](http://www.blue-zero.com/WebSocket/)
哦，你需要打开两个，地址写ws://106.14.34.11:11000/pigroom/ws/123，最后那个123可以换成任意int型，只要两个地址写一样的就行，点击连接，就可以开始聊天拉。
######代码运行
1. 需要安装redis
2. 运行`pip install -r requirements.txt`来安装依赖环境
3. 运行`python firstdemo.py`