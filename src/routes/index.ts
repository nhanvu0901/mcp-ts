import type { FastifyInstance } from "fastify";
import askAgentRoutes from "./ask.agent.route"
export default async function (fastify: FastifyInstance): Promise<void> {
    fastify.register(askAgentRoutes, { prefix: "agent" });
}