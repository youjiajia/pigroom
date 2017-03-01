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
-- Table structure for table `store_item`
--

DROP TABLE IF EXISTS `store_item`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `store_item` (
  `item_id` int(11) NOT NULL AUTO_INCREMENT,
  `create_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `store_id` int(11) NOT NULL,
  `product_id` int(11) NOT NULL,
  `product_num` int(11) NOT NULL,
  `title` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL,
  `credit_type` int(11) NOT NULL,
  `credit_value` int(11) NOT NULL,
  `total_num` int(11) NOT NULL,
  `use_num` int(11) NOT NULL,
  `left_num` int(11) NOT NULL,
  `order` int(11) NOT NULL,
  `identity` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`item_id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `store_item`
--

LOCK TABLES `store_item` WRITE;
/*!40000 ALTER TABLE `store_item` DISABLE KEYS */;
INSERT INTO `store_item` VALUES (1,'2016-04-08 11:24:20',1,1,5000,'5000游米',1,0,20,0,20,1,'5000游米'),(2,'2016-04-08 11:24:20',1,2,1,'鲜花一朵',1,0,20,0,20,2,'鲜花一朵'),(3,'2016-04-08 11:24:20',1,6,30,'30M流量',1,0,20,0,20,3,'30M流量'),(4,'2016-04-08 11:24:20',1,7,1,'途牛券X1',1,0,20,0,20,4,'途牛券'),(5,'2016-04-08 11:24:20',1,9,1,'游戏礼包X1',1,0,20,0,20,5,'游戏礼包'),(6,'2016-04-08 11:24:20',1,5,1,'华为p8手机一部',1,0,20,0,20,6,'华为P8手机'),(7,'2016-04-08 11:24:20',2,4,10,'10M流量',2,150,20,0,20,1,''),(8,'2016-04-08 11:24:20',2,4,30,'30M流量',2,300,20,0,20,2,''),(9,'2016-04-08 11:24:20',2,4,150,'150M流量',2,1000,20,0,20,3,'');
/*!40000 ALTER TABLE `store_item` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2016-04-18 14:20:37
