"""
Natural Language & Reasoning Domain Generator for Dataset A.
Generates comprehensive English prose covering reasoning, epistemology, cognitive science, argumentation, and communication.
"""

from __future__ import annotations

from typing import Any


def get_natural_language_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "natural_language",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "English natural language and reasoning exposition",
            },
        })

    add(
        "sem_nl_001",
        "Deductive reasoning operates from general premises to arrive at logically guaranteed specific conclusions. If the premises are factually true and the syllogistic structure is valid, the conclusion must inevitably be true. In contrast, inductive reasoning moves in the inverse direction, synthesizing specific empirical observations into generalized predictive principles. While inductive inference cannot deliver mathematical certainty, it serves as the foundational epistemological engine of empirical science, machine learning models, and everyday probabilistic decision making.",
        "Deductive vs inductive reasoning comparison",
    )

    add(
        "sem_nl_002",
        "Cognitive biases represent systematic deviations from normative rationality that occur as human brains attempt to simplify complex information processing. The confirmation bias leads individuals to selectively notice, interpret, and recall evidence that substantiates their preexisting beliefs while discounting disconfirming data. In contrast, the availability heuristic causes people to overestimate the probability of events that are readily retrievable from memory, often due to recent emotional salience or media amplification.",
        "Cognitive biases and heuristic decision making",
    )

    add(
        "sem_nl_003",
        "Scientific inquiry relies fundamentally on the principle of falsifiability, famously articulated by philosopher Karl Popper. For a hypothesis to be recognized as genuinely scientific, there must exist some conceivable empirical observation or experimental outcome that could prove it false. Theories that are structured so loosely that no possible evidence could refute them belong to the domain of pseudoscience or dogma, rather than rigorous empirical investigation.",
        "Falsifiability and the scientific method",
    )

    add(
        "sem_nl_004",
        "Effective technical writing prioritizes clarity, conciseness, and contextual relevance over rhetorical embellishment. Authors must tailor their explanatory depth to their audience's foundational knowledge, structuring documents with hierarchical headings, concrete illustrations, and clear transitions. When introducing abstract terminology, grounding definitions in relatable analogues minimizes cognitive load and maximizes knowledge transfer across diverse engineering teams.",
        "Technical writing principles and knowledge transfer",
    )

    add(
        "sem_nl_005",
        "First-principles thinking involves dismantling complex problems into their most fundamental, undeniable truths and reasoning upwards from that baseline. Popularized in physics and modern engineering, this approach prevents teams from relying uncritically on conventional analogies or historical momentum. By questioning inherited assumptions regarding material costs, system constraints, or workflow paradigms, engineers can discover innovative, highly optimized architectural solutions.",
        "First-principles thinking and engineering innovation",
    )

    add(
        "sem_nl_006",
        "Logical fallacies undermine the integrity of reasoned debate by substituting specious argumentation for valid inference. The ad hominem fallacy attacks an opponent's character or motivations rather than engaging their substantive thesis. Similarly, the straw man fallacy distorts or oversimplifies an opposing perspective into an absurd caricature that is easy to dismantle, completely evading the stronger version of the argument.",
        "Common informal logical fallacies",
    )

    add(
        "sem_nl_007",
        "Epistemology investigates the nature, origin, scope, and justification of human knowledge. The classical philosophical definition characterizes knowledge as justified true belief (JTB), requiring that an individual believes a proposition, that the proposition is objectively true, and that the individual possesses adequate justification for holding that belief. However, Edmund Gettier demonstrated through famous counterexamples that justified true belief alone is insufficient, sparking extensive debate regarding epistemic luck and warrant.",
        "Epistemological foundations and Gettier problems",
    )

    add(
        "sem_nl_008",
        "The Sapir-Whorf hypothesis, or linguistic relativity, posits that the structural properties of a particular language influence or determine the cognitive patterns and worldview of its speakers. While the deterministic version of this hypothesis has been widely discredited by modern cognitive linguistics, weaker versions continue to receive empirical support, demonstrating that linguistic categories can shape attention allocation, color perception, spatial orientation, and mnemonic encoding.",
        "Linguistic relativity and cognitive linguistics",
    )

    add(
        "sem_nl_009",
        "Rhetoric, the classical art of persuasive discourse, relies upon the harmonious interplay of three core modes of persuasion: ethos, pathos, and logos. Ethos establishes the credibility, expertise, and moral integrity of the speaker. Pathos connects emotionally with the audience, fostering empathy and shared resonance. Logos appeals to reason, empirical evidence, and logical consistency. A masterfully crafted argument balances all three modes to engage both the intellect and conscience of the listener.",
        "Aristotelian rhetorical appeals (ethos, pathos, logos)",
    )

    add(
        "sem_nl_010",
        "Occam's razor is a foundational heuristic principle attributed to the medieval scholastic philosopher William of Ockham. It dictates that among competing hypotheses that explain a given phenomenon with equal predictive accuracy, the one requiring the fewest explanatory assumptions should be preferred. In software architecture and algorithmic design, Occam's razor strongly advocates for minimalist elegance, avoiding unnecessary complexity and premature abstraction.",
        "Occam's razor and simplicity in systems design",
    )

    add(
        "sem_nl_011",
        "Active listening is an essential conversational competence that involves paying full, deliberate attention to the speaker, comprehending their underlying meaning, and providing thoughtful, clarifying feedback. Rather than mentally rehearsing a rebuttal while the other party is speaking, an active listener reflects summarized viewpoints, asks probing clarifying questions, and observes non-verbal communicative cues, thereby de-escalating interpersonal friction and fostering collaborative alignment.",
        "Active listening and interpersonal communication",
    )

    add(
        "sem_nl_012",
        "The Dunning-Kruger effect describes a metacognitive anomaly wherein individuals with low competence in a specific domain drastically overestimate their abilities, due to lacking the very knowledge required to recognize their deficiency. Conversely, high-performing experts frequently suffer from the imposter phenomenon or assume that tasks which come easily to them are similarly effortless for others, underestimating their relative distinction.",
        "Dunning-Kruger effect and metacognitive awareness",
    )

    add(
        "sem_nl_013",
        "Semiotics is the academic study of signs, symbols, and their interpretation within cultural and communication systems. Pioneered by Ferdinand de Saussure and Charles Sanders Peirce, semiotics distinguishes between the signifier (the physical form or sound representing a concept) and the signified (the mental concept itself). Understanding semiotic relationships allows designers, programmers, and linguists to craft intuitive iconographies, user interfaces, and syntactic vocabularies.",
        "Semiotics, signifiers, and semantic interpretation",
    )

    add(
        "sem_nl_014",
        "Dialectical reasoning, famously refined by Hegel and Marx, explores how intellectual contradictions and competing tensions drive historical, philosophical, and systemic evolution. In a classic dialectic, a thesis encounters its opposing antithesis, producing creative friction that eventually reconciles into a higher-order synthesis. In engineering organizations, rigorous debate between opposing architectural paradigms often generates robust hybrid designs superior to either isolated alternative.",
        "Dialectical reasoning and synthesis of opposing paradigms",
    )

    add(
        "sem_nl_015",
        "Bayesian inference provides a mathematical framework for updating the probability estimate for a hypothesis as new empirical evidence or data becomes available. Starting from a prior probability distribution, the application of Bayes' Theorem calculates a posterior probability by incorporating the likelihood of observing the specific evidence given the hypothesis. This probabilistic approach underlies modern statistical modeling, spam filtering, autonomous vehicle perception, and belief revision.",
        "Bayesian inference and probabilistic belief updating",
    )

    add(
        "sem_nl_016",
        "The principle of charity requires that when interpreting an opponent's argument or statement, one should reconstruct it in its strongest, most rational, and most plausible form before evaluating it. By avoiding bad-faith mischaracterizations and engaging the strongest possible formulation of opposing ideas, thinkers foster constructive discourse, uncover nuanced blind spots in their own perspectives, and elevate intellectual debate.",
        "Principle of charity in rational discourse",
    )

    add(
        "sem_nl_017",
        "Pragmatics in linguistics examines how context influences the interpretation of meaning beyond the literal semantics of spoken or written words. Pragmatic factors include the relationship between conversational participants, background knowledge, social conventions, and implicatures. When someone asks 'Can you pass the salt?', the literal semantic question concerns physical ability, but the pragmatic illocutionary intent is a polite request for action.",
        "Pragmatics, speech acts, and conversational implicature",
    )

    add(
        "sem_nl_018",
        "Heuristic evaluation is an inspection method used in human-computer interaction and usability engineering to systematically identify user interface design flaws against recognized principles. Jakob Nielsen's ten usability heuristics emphasize visibility of system status, match between the system and the real world, user control and freedom, consistency and standards, error prevention, and recognition over recall to maximize software ergonomics.",
        "Usability heuristics and interface design ergonomics",
    )

    add(
        "sem_nl_019",
        "Emergence is a phenomenon wherein a complex entity or system exhibits collective properties and behaviors that its individual constituent components do not possess on their own. In biological systems, single neurons do not experience consciousness, yet their collective neural network generates self-aware intelligence. Similarly, simple algorithmic rules executed across decentralized distributed nodes can give rise to sophisticated swarm intelligence and market equilibria.",
        "Emergent behavior in complex distributed systems",
    )

    add(
        "sem_nl_020",
        "Socratic questioning is a disciplined, pedagogical method of cooperative argumentative dialogue designed to stimulate critical thinking and draw out underlying assumptions. By asking focused, probing questions regarding definitions, evidence, implications, and alternative perspectives, the facilitator guides participants to recognize logical inconsistencies in their beliefs and discover deeper insights autonomously.",
        "Socratic questioning and critical analysis methodology",
    )

    return samples
