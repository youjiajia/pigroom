# pigroom
####导语
>本项目志在构建一个类似于gitter的在线聊天室,使用websocket进行通信，服务端使用python进行架构。

####应用
借助于tornado异步请求非阻塞的特性：http://docs.pythontab.com/tornado/introduction-to-tornado/
消息队列暂定redis的发布订阅模式，使用插件https://github.com/leporo/tornado-redis