import "reflect-metadata";
import { DataSource } from "typeorm";
import config from "../config";

export const AppDataSource = new DataSource({
	connectTimeoutMS: 0,
	migrationsTableName: "migrations",
	migrationsRun: false,    // Run migrations on start
	name: "default",
	type: "postgres",
	host: config.DB_HOST,
	port: config.DB_PORT,
	username: config.DB_USERNAME,
	password: config.DB_PASSWORD,
	database: config.DB_DATABASE,
	entities: [__dirname + "/../**/*.entity.{ts,js}"],
	migrations: ["migrations/**/*.ts"],
	// synchronize: config.NODE_ENV === "development",
	synchronize: false,
	logging: config.NODE_ENV === "development",
	maxQueryExecutionTime: 600000,
	extra: {
		poolSize: 50,
		connectionLimit: 50,
        connectionTimeoutMillis: 3300000,
		query_timeout: 3000000,
    	statement_timeout: 3000000
    }
})