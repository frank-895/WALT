export type DemoStatus =
	| "provisioning"
	| "onboarding"
	| "preparing"
	| "ready"
	| "failed";

export type DemoSession = {
	id: string;
	status: DemoStatus;
	expires_at: string;
	view_url?: string;
	error?: string;
};

type RealtimeEvent = {
	type?: string;
	delta?: string;
};

type VoiceAnswer = {
	sdp: string;
	call_id: string;
};

type DemoCallbacks = {
	onSession: (session: DemoSession) => void;
	onTranscript: (text: string) => void;
	onError: (message: string) => void;
};

export type DemoConnection = {
	close: () => Promise<void>;
};

export async function connectDemo(
	callbacks: DemoCallbacks,
): Promise<DemoConnection> {
	const created = await requestJson<DemoSession>("/api/demo-sessions", {
		method: "POST",
	});
	callbacks.onSession(created);

	const peer = new RTCPeerConnection();
	let microphone: MediaStream | undefined;
	try {
		microphone = await navigator.mediaDevices.getUserMedia({ audio: true });
		const activeMicrophone = microphone;
		for (const track of activeMicrophone.getTracks())
			peer.addTrack(track, activeMicrophone);

		const remoteAudio = new Audio();
		remoteAudio.autoplay = true;
		peer.ontrack = (event) => {
			remoteAudio.srcObject = event.streams[0];
		};

		const events = peer.createDataChannel("oai-events");
		events.addEventListener("message", (message) => {
			const event = JSON.parse(message.data) as RealtimeEvent;
			if (
				(event.type === "response.output_audio_transcript.delta" ||
					event.type === "response.audio_transcript.delta") &&
				event.delta
			) {
				callbacks.onTranscript(event.delta);
			}
		});

		const offer = await peer.createOffer();
		await peer.setLocalDescription(offer);
		const response = await fetch(`/api/demo-sessions/${created.id}/offer`, {
			method: "POST",
			headers: { "Content-Type": "application/sdp" },
			body: offer.sdp,
		});
		if (!response.ok) {
			const payload = (await response.json().catch(() => null)) as {
				detail?: string;
			} | null;
			throw new Error(
				payload?.detail ?? "The voice connection could not be started.",
			);
		}
		const answer = (await response.json()) as VoiceAnswer;
		await peer.setRemoteDescription({ type: "answer", sdp: answer.sdp });
		await waitForChannel(events);
		events.send(JSON.stringify({ type: "response.create" }));

		let stopped = false;
		let polling = false;
		const poll = window.setInterval(async () => {
			if (stopped || polling) return;
			polling = true;
			try {
				const session = await requestJson<DemoSession>(
					`/api/demo-sessions/${created.id}`,
				);
				callbacks.onSession(session);
				if (session.status === "failed") {
					callbacks.onError(session.error ?? "The demo could not be started.");
					window.clearInterval(poll);
				} else if (session.status === "ready") {
					window.clearInterval(poll);
				}
			} catch (error) {
				callbacks.onError(errorMessage(error));
			} finally {
				polling = false;
			}
		}, 1000);

		return {
			async close() {
				stopped = true;
				window.clearInterval(poll);
				for (const track of activeMicrophone.getTracks()) track.stop();
				events.close();
				peer.close();
				await fetch(`/api/demo-sessions/${created.id}`, {
					method: "DELETE",
					keepalive: true,
				});
			},
		};
	} catch (error) {
		for (const track of microphone?.getTracks() ?? []) track.stop();
		peer.close();
		await fetch(`/api/demo-sessions/${created.id}`, {
			method: "DELETE",
			keepalive: true,
		});
		throw error;
	}
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
	const response = await fetch(url, init);
	if (!response.ok) {
		const payload = (await response.json().catch(() => null)) as {
			detail?: string;
		} | null;
		throw new Error(payload?.detail ?? "The demo request failed.");
	}
	return (await response.json()) as T;
}

function waitForChannel(channel: RTCDataChannel): Promise<void> {
	if (channel.readyState === "open") return Promise.resolve();
	return new Promise((resolve, reject) => {
		channel.addEventListener("open", () => resolve(), { once: true });
		channel.addEventListener(
			"error",
			() => reject(new Error("The voice event channel failed.")),
			{ once: true },
		);
	});
}

function errorMessage(error: unknown) {
	return error instanceof Error
		? error.message
		: "The demo encountered an error.";
}
