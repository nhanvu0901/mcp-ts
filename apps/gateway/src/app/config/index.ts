import dotenv from "dotenv";
import path from "node:path";

const NODE_ENV = process.env.NODE_ENV || "development";

dotenv.config({
	path: path.join(__dirname, "..", "..", `.env.${NODE_ENV}`),
});

interface Config {
	HOST: string,
	PORT: number;
    CERTIFICATE_PATH: string;
    CERTIFICATE_KEY_PATH: string;
	DB_HOST: string;
    DB_PORT: number;
    DB_DATABASE: string;
    DB_USERNAME: string;
    DB_PASSWORD: string;
	NODE_ENV: string;
	origin: string | string[];
    TRUST_PROXY: boolean;
    LOG_PATH: string;
    LOG_LEVEL: string;
    LOG_MAX_SIZE: string;
    LOG_DATE_PATTERN: string;
    LOG_FILE_GENERATION_SUPPORT: boolean;
}

const config: Config = {
	HOST: process.env.HOST ?? "localhost",
	PORT: +(process.env.PORT ?? "3000"),
    CERTIFICATE_PATH: process.env.CERTIFICATE_PATH ?? "example.crt",
    CERTIFICATE_KEY_PATH: process.env.CERTIFICATE_KEY_PATH ?? "example.key",
	DB_HOST: process.env.DB_HOST ?? "localhost",
    DB_PORT: +(process.env.DB_PORT ?? 5432),
    DB_DATABASE: process.env.DB_DATABASE ?? "test",
    DB_USERNAME: process.env.DB_USERNAME ?? "admin",
    DB_PASSWORD: process.env.DB_PASSWORD ?? "Admin123",
	NODE_ENV,
	origin: process.env.ALLOWED_ORIGIN?.split(",") || "*",
    TRUST_PROXY: process.env.TLS_TERMINATION_PROXY === "true",
    LOG_PATH: process.env.LOG_PATH ?? "../..",
    LOG_LEVEL: process.env.LOG_LEVEL ?? "info",
    LOG_MAX_SIZE: process.env.LOG_MAX_SIZE ?? "20m",
    LOG_DATE_PATTERN: process.env.LOG_DATE_PATTERN ?? "YYYY-MM-DD",
    LOG_FILE_GENERATION_SUPPORT: process.env.LOG_FILE_GENERATION_SUPPORT === "true"
};

export default config;
