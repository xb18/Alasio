/**
 * Route-group state shared between the layouts and the websocket client.
 *
 * `.public` is true while any (public) route is mounted. Public pages
 * never need a websocket connection: an unauthenticated handshake is
 * accepted then closed(4001) by the backend (a refused handshake would
 * only surface as 1006 to the browser), so connecting there is a
 * guaranteed failure. The (public) layout sets the flag on mount and
 * clears it on destroy; the websocket client refuses to connect while
 * it is set and disconnects (clearing all state) when a public page
 * mounts over an existing connection.
 */
export const routeState = $state({ public: false });
