export type DemoStatus =
	| "provisioning"
	| "onboarding"
	| "preparing"
	| "ready"
	| "failed";

export type VoiceActivity = "idle" | "listening" | "speaking";

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
	transcript?: string;
	error?: {
		message?: string;
	};
};

type VoiceAnswer = {
	sdp: string;
	call_id: string;
};

type DemoCallbacks = {
	onSession: (session: DemoSession) => void;
	onAssistantTranscript: (text: string) => void;
	onUserTranscript: (text: string) => void;
	onVoiceActivity: (activity: VoiceActivity) => void;
	onError: (message: string) => void;
};

export type DemoConnection = {
	close: () => Promise<void>;
};

const ACTIVE_DEMO_SESSION_KEY = "walt-active-demo-session";

export async function connectDemo(
	callbacks: DemoCallbacks,
): Promise<DemoConnection> {
	await deletePreviousDemoSession();
	const created = await requestJson<DemoSession>("/api/demo-sessions", {
		method: "POST",
	});
	setActiveDemoSession(created.id);
	callbacks.onSession(created);

	const peer = new RTCPeerConnection();
	let microphone: MediaStream | undefined;
	let closed = false;
	let poll: number | undefined;
	window.addEventListener("pagehide", handlePageHide);

	function handlePageHide() {
		if (closed) {
			return;
		}

		closed = true;
		stopLocalConnection();
		void deleteDemoSession(created.id, true);
	}

	async function close() {
		if (closed) {
			return;
		}

		closed = true;
		window.removeEventListener("pagehide", handlePageHide);
		stopLocalConnection();
		await deleteDemoSession(created.id, true).catch(() => undefined);
		clearActiveDemoSession(created.id);
	}

	function stopLocalConnection() {
		if (poll !== undefined) {
			window.clearInterval(poll);
		}
		for (const track of microphone?.getTracks() ?? []) {
			track.stop();
		}
		peer.close();
	}

	try {
		microphone = await navigator.mediaDevices.getUserMedia({
			audio: {
				autoGainControl: true,
				echoCancellation: true,
				noiseSuppression: true,
			},
		});
		for (const track of microphone.getTracks()) {
			peer.addTrack(track, microphone);
		}

		const remoteAudio = new Audio();
		remoteAudio.autoplay = true;
		peer.ontrack = (event) => {
			remoteAudio.srcObject = event.streams[0];
		};

		const events = peer.createDataChannel("oai-events");
		let assistantTranscript = "";
		let responseHasTranscript = false;

		events.addEventListener("message", (message) => {
			let event: RealtimeEvent;
			try {
				event = JSON.parse(message.data) as RealtimeEvent;
			} catch {
				return;
			}

			if (event.type === "response.created") {
				responseHasTranscript = false;
				return;
			}

			if (
				(event.type === "response.output_audio_transcript.delta" ||
					event.type === "response.audio_transcript.delta") &&
				event.delta
			) {
				if (!responseHasTranscript) {
					assistantTranscript = "";
					responseHasTranscript = true;
				}
				assistantTranscript += event.delta;
				callbacks.onAssistantTranscript(assistantTranscript);
				callbacks.onVoiceActivity("speaking");
				return;
			}

			if (
				(event.type === "response.output_audio_transcript.done" ||
					event.type === "response.audio_transcript.done") &&
				event.transcript
			) {
				assistantTranscript = event.transcript;
				callbacks.onAssistantTranscript(assistantTranscript);
				callbacks.onVoiceActivity("listening");
				return;
			}

			if (event.type === "input_audio_buffer.speech_started") {
				callbacks.onUserTranscript("");
				callbacks.onVoiceActivity("listening");
				return;
			}

			if (
				event.type ===
					"conversation.item.input_audio_transcription.completed" &&
				event.transcript
			) {
				callbacks.onUserTranscript(event.transcript);
				return;
			}

			if (event.type === "error") {
				callbacks.onError(
					event.error?.message ?? "The voice connection encountered an error.",
				);
				void close();
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
		callbacks.onVoiceActivity("listening");
		events.send(JSON.stringify({ type: "response.create" }));

		let polling = false;
		poll = window.setInterval(async () => {
			if (closed || polling) {
				return;
			}
			polling = true;
			try {
				const session = await requestJson<DemoSession>(
					`/api/demo-sessions/${created.id}`,
				);
				callbacks.onSession(session);
				if (session.status === "failed") {
					callbacks.onError(session.error ?? "The demo could not be started.");
					await close();
				} else if (session.status === "ready" && poll !== undefined) {
					window.clearInterval(poll);
				}
			} catch (pollingError) {
				callbacks.onError(errorMessage(pollingError));
				await close();
			} finally {
				polling = false;
			}
		}, 1000);

		return { close };
	} catch (error) {
		await close();
		throw error;
	}
}

async function deletePreviousDemoSession() {
	const sessionId = activeDemoSession();
	if (!sessionId) {
		return;
	}

	await deleteDemoSession(sessionId);
	clearActiveDemoSession(sessionId);
}

async function deleteDemoSession(sessionId: string, keepalive = false) {
	const response = await fetch(`/api/demo-sessions/${sessionId}`, {
		method: "DELETE",
		keepalive,
	});
	if (!response.ok) {
		throw new Error("The previous demo session could not be cleaned up.");
	}
}

function activeDemoSession() {
	try {
		return window.sessionStorage.getItem(ACTIVE_DEMO_SESSION_KEY);
	} catch {
		return null;
	}
}

function setActiveDemoSession(sessionId: string) {
	try {
		window.sessionStorage.setItem(ACTIVE_DEMO_SESSION_KEY, sessionId);
	} catch {
		return;
	}
}

function clearActiveDemoSession(sessionId: string) {
	try {
		if (activeDemoSession() === sessionId) {
			window.sessionStorage.removeItem(ACTIVE_DEMO_SESSION_KEY);
		}
	} catch {
		return;
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
	if (channel.readyState === "open") {
		return Promise.resolve();
	}
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
