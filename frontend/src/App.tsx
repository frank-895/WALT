import { ArrowUpRight } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";

type OnboardingStage =
	| "landing"
	| "welcome"
	| "role"
	| "outcome"
	| "clarification"
	| "handoff"
	| "demo";

type OnboardingAnswers = {
	role: string;
	outcome: string;
	clarification: string;
};

const QUESTION_EXIT_DURATION_MS = 120;
const HANDOFF_DURATION_MS = 650;

const questions = {
	role: "What kind of work do you do?",
	outcome: "What would you most like to learn from this demo?",
	clarification: "What would a successful outcome look like for you?",
} as const;

const waltLetters = [
	{ letter: "W", meaning: "walkthrough" },
	{ letter: "A", meaning: "agent" },
	{ letter: "L", meaning: "live" },
	{ letter: "T", meaning: "talkative" },
] as const;

function needsClarification(answer: string) {
	const normalizedAnswer = answer.trim().toLowerCase();
	const vagueAnswers = ["anything", "everything", "not sure", "just looking"];
	return (
		normalizedAnswer.split(/\s+/).length < 3 ||
		vagueAnswers.includes(normalizedAnswer)
	);
}

export function App() {
	const answerInput = useRef<HTMLInputElement>(null);
	const [stage, setStage] = useState<OnboardingStage>(
		window.location.hash === "#demo" ? "welcome" : "landing",
	);
	const [answer, setAnswer] = useState("");
	const [activeLetter, setActiveLetter] = useState<number | null>(null);
	const [isQuestionExiting, setIsQuestionExiting] = useState(false);
	const [answers, setAnswers] = useState<OnboardingAnswers>({
		role: "",
		outcome: "",
		clarification: "",
	});

	useEffect(() => {
		function handleLocationChange() {
			setStage(window.location.hash === "#demo" ? "welcome" : "landing");
		}

		window.addEventListener("hashchange", handleLocationChange);
		return () => window.removeEventListener("hashchange", handleLocationChange);
	}, []);

	useEffect(() => {
		if (stage !== "handoff") {
			return;
		}

		const timeout = window.setTimeout(
			() => setStage("demo"),
			HANDOFF_DURATION_MS,
		);
		return () => window.clearTimeout(timeout);
	}, [stage]);

	function transitionTo(nextStage: OnboardingStage) {
		if (isQuestionExiting) {
			return;
		}

		setIsQuestionExiting(true);
		window.setTimeout(() => {
			setAnswer("");
			setStage(nextStage);
			setIsQuestionExiting(false);
			window.requestAnimationFrame(() => answerInput.current?.focus());
		}, QUESTION_EXIT_DURATION_MS);
	}

	function handleAnswer(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		const submittedAnswer = answer.trim();

		if (!submittedAnswer) {
			return;
		}

		if (stage === "role") {
			setAnswers((currentAnswers) => ({
				...currentAnswers,
				role: submittedAnswer,
			}));
			transitionTo("outcome");
			return;
		}

		if (stage === "outcome") {
			setAnswers((currentAnswers) => ({
				...currentAnswers,
				outcome: submittedAnswer,
			}));
			transitionTo(
				needsClarification(submittedAnswer) ? "clarification" : "handoff",
			);
			return;
		}

		if (stage === "clarification") {
			setAnswers((currentAnswers) => ({
				...currentAnswers,
				clarification: submittedAnswer,
			}));
			transitionTo("handoff");
		}
	}

	const isDemo = stage === "demo";
	const demoFocus = answers.clarification || answers.outcome;

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
					<a className="demo-button" href="#demo">
						<span>meet walt</span>
						<span className="demo-button-arrow" aria-hidden="true">
							<ArrowUpRight strokeWidth={2.25} />
						</span>
					</a>
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
			<div className="desktop" aria-label="Virtual machine screen" role="img" />

			<div
				className={`guide-orb ${isDemo ? "guide-orb-demo" : "guide-orb-onboarding"}`}
				aria-label={isDemo ? "Walt is speaking" : "Walt"}
				role="img"
			/>

			{!isDemo && (
				<section className="onboarding" aria-label="Demo onboarding">
					<div
						className="onboarding-step"
						data-exiting={isQuestionExiting}
						key={stage}
					>
						{stage === "welcome" && (
							<>
								<h1>Let’s make this demo useful to you.</h1>
								<button
									className="begin-button"
									type="button"
									onClick={() => transitionTo("role")}
								>
									Begin
								</button>
							</>
						)}

						{(stage === "role" ||
							stage === "outcome" ||
							stage === "clarification") && (
							<>
								<h1>{questions[stage]}</h1>
								<form onSubmit={handleAnswer}>
									<input
										aria-label={questions[stage]}
										autoComplete="off"
										ref={answerInput}
										value={answer}
										onChange={(event) => setAnswer(event.target.value)}
									/>
									<button
										aria-label="Continue"
										disabled={!answer.trim() || isQuestionExiting}
										type="submit"
									>
										→
									</button>
								</form>
							</>
						)}

						{stage === "handoff" && <h1>Perfect. Let’s begin.</h1>}
					</div>
				</section>
			)}

			{isDemo && (
				<div className="narration">
					<p aria-live="polite">
						I’ll focus on {demoFocus}, keeping it relevant to your work in{" "}
						{answers.role}.
					</p>
				</div>
			)}
		</main>
	);
}
