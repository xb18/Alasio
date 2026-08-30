import { withQuery } from "$lib/query";

export interface loginRequest {
  pwd: string;
}

export interface jwtError {
  // error key, e.g. "FAIL2BAN_TOO_MANY_REQUEST", translated on the frontend
  err: string;
  // extra error data, omitted by the backend when empty
  data?: {
    // remaining attempts before ban
    remain?: number;
    // seconds until the ban / cooldown ends
    after?: number;
  };
}

interface authResponseMap {
  200: null;
  204: null;
  401: jwtError;
  403: jwtError;
  429: jwtError;
}

export const authApi = {
  login: withQuery
    .post(`/auth/login`)
    .request<loginRequest>()
    .response<authResponseMap>()
    .caller((pwd: string) => ({
      body: { pwd: pwd },
    }))
    .build(),

  renew: withQuery.get("/auth/renew").withOptions({ credentials: "same-origin" }).response<authResponseMap>().build(),
};
