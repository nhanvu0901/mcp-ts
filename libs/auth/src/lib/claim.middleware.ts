import { claim, Claims } from "./claim.service";
import { FastifyReply, FastifyRequest } from "fastify";

interface ClaimsRequest extends FastifyRequest {
    claims?: Claims;
}

export function extractToken(authorization: string | undefined): string {
    if (!authorization) {
        throw new Error("Authorization token is required");
    }

    const token = authorization.split(" ")[1];

    if (!token) {
        throw new Error("Bearer token is missing");
    }

    return token;
}

export async function extractClaim(token: string): Promise<Claims> {
    const claims = await claim(token);

    if (typeof claims === "object" && claims !== null) {
        return claims as Claims;
    } else {
        throw new Error("Invalid claims format");
    }
}

export async function claimMiddleware(request: ClaimsRequest, reply: FastifyReply) {
    try {
        const token = extractToken(request.headers.authorization);
        const claims = await extractClaim(token);

        request.claims = claims;
    } catch {
        return reply.status(401).send({ error: "Invalid or expired token" });
    }
}
