// import { PlatformContext, ResponseErrorObject } from "@tsed/common";
// import { Env } from "@tsed/core";
// import { Constant } from "@tsed/di";
// import { Catch, ExceptionFilterMethods } from "@tsed/platform-exceptions";
// import { Exception } from "@tsed/exceptions";
// import logger from "../config/logger";

// @Catch(Error, Exception)
// export class ErrorFilter implements ExceptionFilterMethods {
//     @Constant("env")
//     env: Env;

//     catch(exception: Error | Exception, ctx: PlatformContext) {
//         // const { response, logger } = ctx;
//         const { response } = ctx;
//         const error = this.mapError(exception);
//         const headers = this.getHeaders(exception);

//         logger.error(error);

//         response
//             .setHeaders(headers)
//             .status(error.status || 500)
//             .body(error);
//     }

//     mapError(error: any) {
//         return {
//             name: error.origin?.name || error.name,
//             code: error.code || "",
//             message: error.message,
//             status: error.status || 500,
//             errors: this.getErrors(error),
//             stack: this.env === Env.DEV ? error.stack : undefined,
//             origin: {
//                 ...error.origin || {},
//                 errors: undefined
//             },
//         };
//     }

//     protected getErrors(error: any) {
//         return [error, error.origin].filter(Boolean).reduce((errs, { errors }: ResponseErrorObject) => {
//             return [...errs, ...(errors || [])];
//         }, []);
//     }

//     protected getHeaders(error: any) {
//         return [error, error.origin].filter(Boolean).reduce((obj, { headers }: ResponseErrorObject) => {
//             return {
//                 ...obj,
//                 ...(headers || {})
//             };
//         }, {});
//     }
// }