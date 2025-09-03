import jwt, { JwtHeader, SigningKeyCallback } from "jsonwebtoken";
import axios from "axios";
import jwkToPem from "jwk-to-pem";
import dotenv from "dotenv";
import https from "https";

dotenv.config();

export interface Claims {
    sub: string;
    exp: number;
}

interface JWK {
    kid: string;
    kty: string;
    alg: string;
    use: string;
    x5c: string[];
    n: string;
    e: string;
}

interface JWKS {
    keys: JWK[];
}

let cachedKeys: JWKS | null = null;
let cachedPublicKey: string | null = null;

async function getPublicKeys() {
    if (cachedKeys) return cachedKeys;

    const publicKeyOrUrl = process.env.PUBLIC_KEY;
    if (!publicKeyOrUrl) throw new Error("Missing PUBLIC_KEY in env");

    // Ak PUBLIC_KEY obsahuje cert
    if (publicKeyOrUrl.startsWith("-----BEGIN CERTIFICATE-----")) {
        cachedPublicKey = publicKeyOrUrl;
        return null; // V tomto prípade sa JWKS nevyužíva
    }

    // Ak PUBLIC_KEY obsahuje URL
    const httpsAgent = new https.Agent({
        rejectUnauthorized: false,
    });

    const res = await axios.get<JWKS>(publicKeyOrUrl, { httpsAgent });
    cachedKeys = res.data;
    return cachedKeys;
}

function getKey(header: JwtHeader, callback: SigningKeyCallback): void {
    getPublicKeys()
        .then((jwks) => {
            if (cachedPublicKey) {
                callback(null, cachedPublicKey);
                return;
            }

            const key = jwks?.keys.find((k) => k.kid === header.kid && k.use === "sig");

            if (!key) {
                callback(new Error("Public key not found"));
                return;
            }

            const pem = jwkToPem({
                kty: "RSA",
                n: key.n,
                e: key.e,
            });
            callback(null, pem);
        })
        .catch((err) => {
            callback(err as Error, undefined);
        });
}

export async function claim(token: string) {
    return new Promise((resolve, reject) => {
        jwt.verify(token, getKey, { algorithms: ["RS256"] }, (err, decoded) => {
            if (err) {
                reject(err);
                return;
            }
            const claims = decoded as Claims;
            resolve(claims);
        });
    });
}
