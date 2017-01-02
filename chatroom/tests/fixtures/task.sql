-- MySQL dump 10.13  Distrib 5.6.22, for osx10.10 (x86_64)
--
-- Host: localhost    Database: migu_community
-- ------------------------------------------------------
-- Server version	5.6.22

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `task`
--

DROP TABLE IF EXISTS `task`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `task` (
  `task_id` int(11) NOT NULL AUTO_INCREMENT,
  `create_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `title` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `image` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `task_type` int(11) NOT NULL,
  `action` int(11) NOT NULL,
  `game_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `num` int(11) NOT NULL,
  `product_id` int(11) NOT NULL,
  `product_num` int(11) NOT NULL,
  `task_platform` int(11) NOT NULL DEFAULT 1,
  `activity_id` VARCHAR(64) default "",
  PRIMARY KEY (`task_id`)
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `task`
--

LOCK TABLES `task` WRITE;
/*!40000 ALTER TABLE `task` DISABLE KEYS */;
INSERT INTO `task` VALUES (1,'2016-03-09 14:43:28','每日签到','每日签到','',2,1,'',1,1,100,1,''),(2,'2016-03-09 14:45:34','观看视频','观看1次视频','',2,2,'',1,1,100,1,''),(3,'2016-03-09 14:47:45','发布视频','发布1次视频','',2,3,'',1,1,800,1,''),(4,'2016-03-09 14:48:30','发表评论','发表1次评论','',2,4,'',1,1,100,1,''),(5,'2016-03-09 14:49:05','分享视频','分享1次视频','',2,5,'',1,1,200,1,''),(6,'2016-03-09 14:49:54','设置头像','设置头像','',1,6,'',1,1,100,1,''),(7,'2016-03-09 14:50:27','订阅游戏','订阅游戏1次','',1,7,'',1,1,100,1,''),(8,'2016-03-09 14:51:03','关注主播','关注主播1次','',1,8,'',1,1,100,1,''),(9,'2016-03-09 14:51:30','发表评论','发表评论1次','',1,4,'',1,1,100,1,''),(10,'2016-03-09 14:51:57','下载游戏','下载游戏1次','',1,9,'',1,1,200,1,''),(11,'2016-03-09 14:52:28','发布视频','发布视频1次','',1,3,'',1,1,100,1,''),(12,'2016-03-09 14:52:45','分享视频','分享视频1次','',1,5,'',1,1,100,1,''),(13,'2016-03-09 15:06:30','刀塔传奇','下载刀塔传奇','',3,9,'55efe64deb43a14b0fcff4e1',1,10,200,1,''),(14,'2016-03-09 14:43:28','分享直播','分享直播','',2,10,'',1,1,150,1,''),(15,'2016-03-09 14:43:28','观看直播','观看直播','',2,11,'',1,1,100,1,'');
/*!40000 ALTER TABLE `task` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2016-03-10  9:54:06
