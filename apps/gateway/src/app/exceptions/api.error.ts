// import { ErrorCode } from "./error.code";
//
// export class ApiError extends Error {
//     status: number;
//     code: ErrorCode;
//     message: string;
//     errors?: any;
//     path: string;
//
//     constructor(status: any, code: ErrorCode, message: string, errors?: any) {
//         super();
//         this.status = status;
//         this.code = code;
//         this.message = message;
//         this.errors = errors;
//     }
//
//     static BadRequest(message: string, errors = []) {
//         return new ApiError(400, ErrorCode.BadRequest, message);
//     }
//
//     static UnauthorizedError() {
//         return new ApiError(401, ErrorCode.Unauthenticated, 'User is not authorized');
//     }
//
//     static ForbiddenError() {
//         return new ApiError(403, ErrorCode.Unauthenticated, 'Access denied');
//     }
//
//     static NotFoundError(message: string) {
//         return new ApiError(404, ErrorCode.NotFound, message,);
//     }
//
//     static UnknownError(error: any, message?: string | undefined) {
//         return new ApiError(500, ErrorCode.UnknownError, error !== null ? error.message : message || "");
//     }
//
//     static ValidationError(message: string, errors: any) {
//         return new ApiError(400, ErrorCode.ValidationError, message, errors);
//     }
// }