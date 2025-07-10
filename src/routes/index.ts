import type { FastifyInstance } from "fastify";
import documentRoutes from "./document.route";
import askAgentRoutes from "./ask.agent.route"
export default async function (fastify: FastifyInstance): Promise<void> {
    fastify.register(documentRoutes, { prefix: "documents" });
    fastify.register(askAgentRoutes, { prefix: "agent" });
}