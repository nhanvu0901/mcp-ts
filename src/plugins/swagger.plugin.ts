import type { FastifyInstance } from "fastify";
import fp from "fastify-plugin";

const swaggerPlugin = async (fastify: FastifyInstance) => {
	fastify.register(import("@fastify/swagger"), {
		openapi: {
			openapi: "3.0.0",
			info: {
				title: "NODE TEMPLATE",
				description: "Node Template API",
				termsOfService: "http://example.com/terms/",
                contact: {
                    name: "Developer",
                    url: "http://www.example.com/support",
                    email: "support@example.com",
                },
                license: {
                    name: "Apache 2.0",
                    url: "https://www.apache.org/licenses/LICENSE-2.0.html",
                },
				version: "0.0.1",
			},
			// components: {
			// 	securitySchemes: {
			// 		bearerAuth: {
			// 			type: "http",
			// 			scheme: "bearer",
			// 		},
			// 	},
			// },
			// security: [
			// 	{
			// 		bearerAuth: [],
			// 	},
			// ],
		},
	});
	fastify.register(import("@fastify/swagger-ui"), { routePrefix: "/docs" });
};

export default fp(swaggerPlugin, {
	name: "swagger",
});
