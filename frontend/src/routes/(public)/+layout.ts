import { websocketClient } from "$lib/ws";
import { routeState } from "$lib/ws/route-state.svelte";
import type { LayoutLoad } from "./$types";

export const load: LayoutLoad = async () => {
  // Public pages must not hold a websocket connection: the backend
  // accepts the handshake then closes it with 4001 (a refused handshake
  // would only surface as 1006 to the browser), so connecting here is a
  // guaranteed failure. The flag is set in load rather than in the
  // layout's onMount because load runs before any component is created
  // or destroyed: the outgoing private page's unsubscribe still calls
  // connect(), and this guard must already be active for that call (and
  // for the incoming page's subscriptions) to be skipped. Tear down a
  // connection a private session left behind and clear all topic state.
  routeState.public = true;
  websocketClient.disconnect();
  return {};
};
