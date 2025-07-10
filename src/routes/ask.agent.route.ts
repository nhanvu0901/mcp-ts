import {FastifyInstance} from "fastify";
import {AskAgentSchema} from "@/routes/schema/ask.agent.schema";
import {AskAgentController} from "@controllers/ask.agent.controller";

async function askAgentRoutes(server: FastifyInstance): Promise<void> {
    server.route({
        url: "/ask",
        method: "POST",
        schema:AskAgentSchema,
        handler:AskAgentController.askAgent
    })
}
export default askAgentRoutes;