-- Ajoute les trois colonnes de statistiques si elles sont absentes.
-- Les anciennes lignes reçoivent la valeur par défaut 0; aucune donnée n'est supprimée.
-- Cette procédure évite de dépendre de ALTER TABLE ... ADD COLUMN IF NOT EXISTS,
-- qui n'est pas disponible dans toutes les versions de MariaDB.

DROP PROCEDURE IF EXISTS simulation_trafic.migration_stats;

DELIMITER //
CREATE PROCEDURE simulation_trafic.migration_stats()
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = 'simulation_trafic'
          AND TABLE_NAME = 'statistiques'
          AND COLUMN_NAME = 'temps_moyen_trajet'
    ) THEN
        ALTER TABLE simulation_trafic.statistiques
            ADD COLUMN temps_moyen_trajet DOUBLE NOT NULL DEFAULT 0;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = 'simulation_trafic'
          AND TABLE_NAME = 'statistiques'
          AND COLUMN_NAME = 'vehicules_attente_feu'
    ) THEN
        ALTER TABLE simulation_trafic.statistiques
            ADD COLUMN vehicules_attente_feu INT NOT NULL DEFAULT 0;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = 'simulation_trafic'
          AND TABLE_NAME = 'statistiques'
          AND COLUMN_NAME = 'vehicules_bouchon'
    ) THEN
        ALTER TABLE simulation_trafic.statistiques
            ADD COLUMN vehicules_bouchon INT NOT NULL DEFAULT 0;
    END IF;
END//
DELIMITER ;

CALL simulation_trafic.migration_stats();
DROP PROCEDURE simulation_trafic.migration_stats;
