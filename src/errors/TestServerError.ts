import { BaseError } from "./BaseError";

export class TestServerdError extends BaseError {
	constructor(name: string, message: string, statusCode: number) {
		super(name, message, statusCode);
	}
}
