DROP TABLE IF EXISTS `bug_report`;

CREATE TABLE `bug_report` (
  `report_id` int(11) NOT NULL AUTO_INCREMENT,
  `create_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `err_type` varchar(128) NOT NULL DEFAULT '',
  `exception` varchar(64) NOT NULL DEFAULT '',
  `phone_model` varchar(32) NOT NULL DEFAULT '',
  `os_version` varchar(32) NOT NULL DEFAULT '',
  `phone_number` varchar(16) NOT NULL DEFAULT '',
  `app_version` varchar(16) NOT NULL DEFAULT '',
  `err_msg` text NOT NULL,
  `err_app` int(11) NOT NULL DEFAULT 0,
  `extention` text,
  PRIMARY KEY (`report_id`)
) ENGINE=MyISAM AUTO_INCREMENT=1 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;