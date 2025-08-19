import * as path from "path";
import type { FastifyInstance } from "fastify";
import AutoLoad from "@fastify/autoload";

/* eslint-disable-next-line */
export interface AppOptions {}

export async function app(fastify: FastifyInstance, opts: AppOptions) {
    // Place here your custom code!

    // Do not touch the following lines

    // This loads all plugins defined in plugins
    // those should be support plugins that are reused
    // through your application
    fastify.register(AutoLoad, {
        dir: path.join(__dirname, "plugins"),
        options: { ...opts },
    });

    // This loads all plugins defined in routes
    // define your routes in one of these
    fastify.register(AutoLoad, {
        dir: path.join(__dirname, "routes"),
        options: { ...opts },
    });
}

// import { fileURLToPath } from "url";
// import { dirname, join } from "path";
// import { FastifyInstance } from "fastify";
// import AutoLoad from "@fastify/autoload";

// /* eslint-disable-next-line */
// export interface AppOptions {}

// // Simulácia __dirname pre ECMAScript moduly
// const __filename = fileURLToPath(import.meta.url);
// const __dirname = dirname(__filename);

// export async function app(fastify: FastifyInstance, opts: AppOptions) {
//     // Place here your custom code!

//     // Do not touch the following lines

//     // This loads all plugins defined in plugins
//     // those should be support plugins that are reused
//     // through your application
//     fastify.register(AutoLoad, {
//         dir: join(__dirname, "plugins"),
//         options: { ...opts },
//     });

//     // This loads all plugins defined in routes
//     // define your routes in one of these
//     fastify.register(AutoLoad, {
//         dir: join(__dirname, "routes"),
//         options: { ...opts },
//     });
// }
