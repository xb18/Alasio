/**
 * Frontend login state.
 *
 * The JWT lives in an HttpOnly cookie, so JavaScript cannot read it
 * directly; this rune is the frontend's source of truth for "logged
 * in". It is set by the login page (successful login) and the (private)
 * layout load (renew check), and cleared when the websocket layer
 * observes an authentication failure (close code 4001).
 *
 * The websocket client consults it before connecting: an
 * unauthenticated handshake is accepted then closed(4001) by the
 * backend (a refused handshake would only surface as 1006 to the
 * browser), so connecting while logged out is a guaranteed failure plus
 * an auth-failure redirect.
 */
export const authState = $state({ loggedIn: false });
