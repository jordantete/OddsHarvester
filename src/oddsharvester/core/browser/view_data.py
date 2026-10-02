"""What the data a match view rendered says about itself: its market, its period and the markets the match offers.

The view decrypts each data answer with WebCrypto and renders it; a gzip JSON body
`{"d": {"bt": <market id>, "sc": <scope>, "nav": {<market id>: ...}, "encodeventId": <event id>}}`.
"""

# Installed in every browser context, it records a summary of each decrypted view data answer in
# window.__ohViewData, read as the view reads it: up to three gzip layers, JSON cut at a trailing error, and a
# market offered when one of its periods lists a bookmaker. Only the top frame, where the view decrypts, is wrapped;
# the Proxy keeps decrypt's arguments, `this` and returned promise, and the summary is built after the view got it.
VIEW_DATA_HOOK_JS = """
(() => {
    if (window !== window.top) return;
    const subtle = globalThis.crypto && globalThis.crypto.subtle;
    if (!subtle || typeof DecompressionStream === 'undefined') return;
    const gunzip = async (bytes) => new Uint8Array(
        await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer()
    );
    const parse = (text) => {
        try {
            return JSON.parse(text);
        } catch (error) {
            const at = /at position (\\d+)/.exec(String(error.message));
            if (!at) throw error;
            return JSON.parse(text.slice(0, Number(at[1])));
        }
    };
    const record = async (plain) => {
        try {
            let bytes = new Uint8Array(plain);
            for (let layer = 0; layer < 3 && bytes[0] === 0x1f && bytes[1] === 0x8b; layer++) {
                bytes = await gunzip(bytes);
            }
            const data = parse(new TextDecoder().decode(bytes)).d;
            if (!data || data.bt === undefined || !data.encodeventId) return;
            const offered = Object.entries(data.nav || {})
                .filter(([, periods]) => Object.values(periods || {}).some((ids) => Array.isArray(ids) && ids.length))
                .map(([market]) => Number(market));
            (window.__ohViewData ||= []).push({
                event: data.encodeventId,
                market: Number(data.bt),
                scope: Number(data.sc),
                offered,
            });
        } catch (e) {}
    };
    const prototype = Object.getPrototypeOf(subtle);
    prototype.decrypt = new Proxy(prototype.decrypt, {
        apply(target, self, args) {
            const result = Reflect.apply(target, self, args);
            result.then(record, () => {});
            return result;
        },
    });
})();
"""

# The view data recorded for `event` since the switch, once one is of `market` or shows the match lacks it.
VIEW_DATA_JS = """
(args) => {
    const records = (window.__ohViewData || []).filter((r) => r.event === args.event);
    const settled = records.some((r) => r.market === args.market || !r.offered.includes(args.market));
    return settled ? records : false;
}
"""

VIEW_DATA_RECORDED_JS = "(event) => (window.__ohViewData || []).filter((r) => r.event === event)"
