CREATE DATABASE IF NOT EXISTS simulation_trafic
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE simulation_trafic;

CREATE TABLE IF NOT EXISTS statistiques (
    id INT NOT NULL AUTO_INCREMENT,
    date_mesure DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    vehicules_actifs INT NOT NULL,
    vehicules_arrives INT NOT NULL,
    vehicules_prioritaires INT NOT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB;
