import { FastifyInstance } from "fastify";
import { AskAgentSchema } from "../routes/schema/ask.agent.schema";
import { AskAgentController } from "../controllers/ask.agent.controller";
import { claimMiddleware } from "@ai-gateway/auth";

async function askAgentRoutes(server: FastifyInstance): Promise<void> {
    server.route({
        url: "/ask",
        method: "POST",
        schema: AskAgentSchema,
        preHandler: [claimMiddleware],
        handler: AskAgentController.askAgent,
    });
}
export default askAgentRoutes;
