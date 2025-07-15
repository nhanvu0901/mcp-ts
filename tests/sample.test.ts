import { expect } from 'chai';
import request from 'supertest';
import buildServer from '@src/main';
import { beforeEach, describe, it } from 'node:test';

describe("Sample Test Controller", () => {
    let server: any;

    beforeEach(async function () {
        // This runs before each test
        server = await buildServer();
    });

    it('It should return hello world ', async function () {
        const result = await request(server.server).get('/test/hello-world');

        expect(result).to.equal('Hello, World!');
    });
});