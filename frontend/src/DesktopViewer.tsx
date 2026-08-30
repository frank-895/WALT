import RFB from "@novnc/novnc";
import { useEffect, useRef, useState } from "react";
import "./DesktopViewer.css";

type DesktopViewerProps = {
	previewUrl?: string;
};

type ConnectionStatus = "waiting" | "connecting" | "connected" | "failed";

function getWebSocketUrl(previewUrl: string) {
	const url = new URL(previewUrl);
	url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
	url.pathname = `${url.pathname.replace(/\/$/, "")}/websockify`;
	return url.toString();
}

export function DesktopViewer({ previewUrl }: DesktopViewerProps) {
	const container = useRef<HTMLElement>(null);
	const [status, setStatus] = useState<ConnectionStatus>(
		previewUrl ? "connecting" : "waiting",
	);

	useEffect(() => {
		if (!container.current || !previewUrl) {
			setStatus("waiting");
			return;
		}

		setStatus("connecting");
		const rfb = new RFB(container.current, getWebSocketUrl(previewUrl), {
			shared: true,
			wsProtocols: ["binary"],
		});
		rfb.viewOnly = true;
		rfb.focusOnClick = false;
		rfb.scaleViewport = true;
		rfb.resizeSession = false;
		rfb.background = "#000";

		const handleConnect = () => setStatus("connected");
		const handleDisconnect = () => setStatus("failed");

		rfb.addEventListener("connect", handleConnect);
		rfb.addEventListener("disconnect", handleDisconnect);

		return () => {
			rfb.removeEventListener("connect", handleConnect);
			rfb.removeEventListener("disconnect", handleDisconnect);
			rfb.disconnect();
		};
	}, [previewUrl]);

	return (
		<section
			aria-label="Atomic CRM controlled by Walt"
			className="desktop-viewer"
			data-status={status}
			ref={container}
		>
			{status !== "waiting" && status !== "connected" && (
				<span className="desktop-viewer-status" role="status">
					{status === "failed" ? "Desktop unavailable" : "Connecting…"}
				</span>
			)}
		</section>
	);
}
