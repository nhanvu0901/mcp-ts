import { expect as chaiExpect } from 'chai';
import dotenv from 'dotenv';
import path from "node:path";

const NODE_ENV = process.env.NODE_ENV ?? "development";

dotenv.config({
	path: path.join(__dirname, "..", "..", `.env.${NODE_ENV}`),
});

(global as any).expect = chaiExpect;