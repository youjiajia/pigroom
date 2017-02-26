#About the plan of devekopment

1、shinx environment deploy
> * start on February 26,2017
> * first,we save the chat record data in redis use List type,and we save 100 cartons of records,this means this list's lenth is 100.
> * second,we save user and room data in mysql,including User,Friendship,Room,Roommerber
> * last,we can use django.We use mysql and redis,because we do not save chat records forever,and the data strcture relatively fixed.
> * over

2、database plan	==>oneday
3、model layer==>three days
4、views layer==>three days
5、unit test module==>two days
6、websocket service repair==>one day
7、services deploy and test,with h5 online==>one day
8、travis，codecov，scrutinizer and others update==>three days
9、docker container make and deploy==>four days
10、performance assessment==>four days