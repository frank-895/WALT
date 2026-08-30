declare module "@novnc/novnc" {
	type RFBOptions = {
		shared?: boolean;
		wsProtocols?: string[];
	};

	export default class RFB extends EventTarget {
		constructor(target: Element, url: string, options?: RFBOptions);

		viewOnly: boolean;
		focusOnClick: boolean;
		scaleViewport: boolean;
		resizeSession: boolean;
		background: string;

		addEventListener(type: "connect", listener: (event: Event) => void): void;
		addEventListener(
			type: "disconnect",
			listener: (event: Event) => void,
		): void;
		removeEventListener(
			type: "connect",
			listener: (event: Event) => void,
		): void;
		removeEventListener(
			type: "disconnect",
			listener: (event: Event) => void,
		): void;
		disconnect(): void;
	}
}
