import { ArrowUpRight, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { DesktopViewer } from "./DesktopViewer";
import {
	connectDemo,
	type DemoConnection,
	type DemoSession,
	type VoiceActivity,
} from "./realtime";

type ExperienceStage =
	| "landing"
	| "connecting"
	| "conversation"
	| "preparing"
	| "handoff"
	| "demo"
	| "error";

const HANDOFF_DURATION_MS = 700;

const waltLetters = [
	{ letter: "W", meaning: "walkthrough" },
	{ letter: "A", meaning: "agent" },
	{ letter: "L", meaning: "live" },
	{ letter: "T", meaning: "talkative" },
] as const;

const voiceActivityLabels: Record<VoiceActivity, string> = {
	idle: "Getting ready",
	listening: "Listening",
	speaking: "Walt is speaking",
};

export function App() {
	const demoConnection = useRef<DemoConnection | null>(null);
	const isConnecting = useRef(false);
	const [stage, setStage] = useState<ExperienceStage>(
		window.location.hash === "#demo" ? "connecting" : "landing",
	);
	const [activeLetter, setActiveLetter] = useState<number | null>(null);
	const [assistantTranscript, setAssistantTranscript] = useState("");
	const [userTranscript, setUserTranscript] = useState("");
	const [voiceActivity, setVoiceActivity] = useState<VoiceActivity>("idle");
	const [viewUrl, setViewUrl] = useState<string | null>(null);
	const [isDesktopLoaded, setIsDesktopLoaded] = useState(false);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		function handleLocationChange() {
			if (window.location.hash === "#demo") {
				setStage((currentStage) =>
					currentStage === "landing" ? "connecting" : currentStage,
				);
				return;
			}

			void demoConnection.current?.close();
			demoConnection.current = null;
			setStage("landing");
		}

		window.addEventListener("hashchange", handleLocationChange);
		window.addEventListener("popstate", handleLocationChange);
		return () => {
			window.removeEventListener("hashchange", handleLocationChange);
			window.removeEventListener("popstate", handleLocationChange);
		};
	}, []);

	useEffect(() => {
		return () => {
			void demoConnection.current?.close();
		};
	}, []);

	useEffect(() => {
		if (stage !== "handoff" || !isDesktopLoaded) {
			return;
		}

		const timeout = window.setTimeout(
			() => setStage("demo"),
			HANDOFF_DURATION_MS,
		);
		return () => window.clearTimeout(timeout);
	}, [isDesktopLoaded, stage]);

	const handleSessionUpdate = useCallback((session: DemoSession) => {
		if (session.status === "onboarding") {
			setStage("conversation");
		}
		if (session.status === "preparing") {
			setStage("preparing");
		}
		if (session.status === "ready" && session.view_url) {
			setViewUrl(session.view_url);
			setStage("handoff");
		}
	}, []);
	const handleDesktopReady = useCallback(() => setIsDesktopLoaded(true), []);

	const startVoiceSession = useCallback(async () => {
		if (isConnecting.current) {
			return;
		}

		isConnecting.current = true;
		setError(null);
		setAssistantTranscript("");
		setUserTranscript("");
		setVoiceActivity("idle");
		setViewUrl(null);
		setIsDesktopLoaded(false);
		setStage("connecting");

		try {
			await demoConnection.current?.close();
			const connection = await connectDemo({
				onSession: handleSessionUpdate,
				onAssistantTranscript: setAssistantTranscript,
				onUserTranscript: setUserTranscript,
				onVoiceActivity: setVoiceActivity,
				onError: (message) => {
					setError(message);
					setStage("error");
				},
			});
			if (window.location.hash !== "#demo") {
				await connection.close();
				return;
			}
			demoConnection.current = connection;
			setStage((currentStage) =>
				currentStage === "connecting" ? "conversation" : currentStage,
			);
		} catch (connectionError) {
			setError(errorMessage(connectionError));
			setStage("error");
		} finally {
			isConnecting.current = false;
		}
	}, [handleSessionUpdate]);

	useEffect(() => {
		if (
			stage === "connecting" &&
			window.location.hash === "#demo" &&
			!demoConnection.current &&
			!isConnecting.current
		) {
			void startVoiceSession();
		}
	}, [stage, startVoiceSession]);

	function openDemo() {
		window.history.pushState(null, "", "#demo");
		void startVoiceSession();
	}

	const isDemo = stage === "demo";
	const isVoiceActive =
		stage === "connecting" ||
		stage === "conversation" ||
		stage === "preparing" ||
		stage === "handoff";

	if (stage === "landing") {
		return (
			<main className="landing">
				<section className="landing-hero">
					<h1 className="walt-lockup" aria-label="WALT">
						{waltLetters.map(({ letter, meaning }, index) => (
							<span
								className="walt-letter-item"
								data-active={activeLetter === index}
								key={letter}
							>
								<button
									aria-label={`${letter} means ${meaning}`}
									aria-pressed={activeLetter === index}
									className="walt-letter"
									onClick={() =>
										setActiveLetter((currentLetter) =>
											currentLetter === index ? null : index,
										)
									}
									type="button"
								>
									<span aria-hidden="true">{letter}</span>
								</button>
								<span className="letter-meaning" aria-hidden="true">
									{meaning}
								</span>
							</span>
						))}
					</h1>
					<button className="demo-button" type="button" onClick={openDemo}>
						<span>meet walt</span>
						<span className="demo-button-arrow" aria-hidden="true">
							<ArrowUpRight strokeWidth={2.25} />
						</span>
					</button>
				</section>

				<section className="pricing" aria-labelledby="pricing-title">
					<header className="pricing-header">
						<p>Pricing</p>
						<h2 id="pricing-title">Free, for now.</h2>
					</header>

					<article className="pricing-card">
						<div className="pricing-plan">
							<p>The only plan</p>
							<h3>$0</h3>
							<span>
								until the remaining credits become zero remaining credits.
							</span>
						</div>

						<ul>
							<li>Everything currently in the demo</li>
							<li>No checkout, invoices, or payment details</li>
							<li>No account to create and therefore none to forget</li>
							<li>
								Availability is directly correlated with our credit balance
							</li>
						</ul>
					</article>

					<p className="pricing-disclaimer">
						If the demo stops, the pricing experiment has concluded.
					</p>
				</section>
			</main>
		);
	}

	return (
		<main className="experience" data-stage={stage}>
			<div className="desktop">
				<DesktopViewer
					onReady={handleDesktopReady}
					previewUrl={viewUrl ?? undefined}
				/>
			</div>

			<div
				className={`guide-orb ${isDemo ? "guide-orb-demo" : "guide-orb-onboarding"}`}
				data-activity={voiceActivity}
				aria-hidden="true"
			/>

			{!isDemo && (
				<section className="onboarding" aria-label="Voice demo onboarding">
					<header className="onboarding-header">
						<strong>WALT</strong>
						<VoiceStatus
							activity={stage === "preparing" ? "idle" : voiceActivity}
							label={
								stage === "preparing"
									? "Building your demo"
									: stage === "handoff"
										? "Desktop ready"
										: stage === "connecting"
											? "Connecting"
											: stage === "error"
												? "Connection lost"
												: voiceActivityLabels[voiceActivity]
							}
						/>
					</header>

					<div className="onboarding-step" key={stage}>
						{stage === "connecting" && <h1>Getting Walt on the line…</h1>}

						{stage === "conversation" && (
							<>
								<h1 className="voice-question" aria-live="polite">
									{assistantTranscript || "Tell me briefly about your company."}
								</h1>
								{userTranscript && (
									<p className="user-transcript">“{userTranscript}”</p>
								)}
							</>
						)}

						{stage === "preparing" && <h1>Got it. Building your demo…</h1>}

						{stage === "handoff" && <h1>Your demo is ready.</h1>}

						{stage === "error" && (
							<div className="onboarding-error">
								<h1>Walt lost the line.</h1>
								<p role="alert">
									{error ?? "The voice session could not be started."}
								</p>
								<button
									className="begin-button"
									type="button"
									onClick={startVoiceSession}
								>
									<RotateCcw aria-hidden="true" />
									Try again
								</button>
							</div>
						)}
					</div>
				</section>
			)}

			{isDemo && (
				<div className="narration" data-activity={voiceActivity}>
					<span className="narration-status" aria-hidden="true" />
					<p aria-live="polite">
						{assistantTranscript || "Walt is ready when you are."}
					</p>
				</div>
			)}

			<span className="sr-only" aria-live="polite">
				{isVoiceActive ? voiceActivityLabels[voiceActivity] : ""}
			</span>
		</main>
	);
}

type VoiceStatusProps = {
	activity: VoiceActivity;
	label: string;
};

function VoiceStatus({ activity, label }: VoiceStatusProps) {
	return (
		<p className="voice-status" data-activity={activity}>
			<span aria-hidden="true">
				<i />
				<i />
				<i />
			</span>
			{label}
		</p>
	);
}

function errorMessage(error: unknown) {
	if (error instanceof DOMException && error.name === "NotAllowedError") {
		return "Microphone access is off. Allow it in your browser, then try again.";
	}
	return error instanceof Error
		? error.message
		: "The voice session could not be started.";
}
