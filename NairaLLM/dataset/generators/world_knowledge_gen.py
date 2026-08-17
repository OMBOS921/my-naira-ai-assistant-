"""
World Knowledge, Science & Humanities Domain Generator for Dataset A.
Generates comprehensive English prose covering physics, astronomy, chemistry, biology, economics, history, and philosophy.
"""

from __future__ import annotations

from typing import Any


def get_world_knowledge_samples() -> list[dict[str, Any]]:
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
                "notes": notes or "World knowledge, science, and humanities foundational exposition",
            },
        })

    add(
        "sem_wk_001",
        "Albert Einstein's General Theory of Relativity, published in 1915, fundamentally transformed theoretical physics by reinterpreting gravity not as an invisible Newtonian attractive force between masses, but as the geometric curvature of four-dimensional spacetime caused by mass and energy. Massive celestial bodies like stars and black holes warp the spacetime fabric around them, causing nearby objects and light photons to follow curved geodesic trajectories. General relativity successfully predicted gravitational lensing, gravitational time dilation, and the emission of gravitational waves detected by LIGO.",
        "General Theory of Relativity and spacetime curvature",
    )

    add(
        "sem_wk_002",
        "Quantum mechanics describes physical phenomena at atomic and subatomic scales where classical Newtonian mechanics ceases to apply. Central principles include wave-particle duality (photons and electrons exhibit properties of both continuous waves and discrete particles), Heisenberg's Uncertainty Principle (asserting fundamental mathematical limits on the precision of simultaneously measuring conjugate variables like position and momentum), and Quantum Entanglement (where the quantum states of entangled particles remain correlated regardless of physical separation).",
        "Quantum mechanics foundations (Wave-particle duality, Uncertainty principle)",
    )

    add(
        "sem_wk_003",
        "DNA (Deoxyribonucleic acid) is the biological macromolecule that encodes genetic instructions for the development, functioning, growth, and reproduction of all known cellular organisms. Structurally arranged as a double helix composed of alternating sugar-phosphate backbones and four nitrogenous bases—Adenine (A), Thymine (T), Cytosine (C), and Guanine (G)—DNA replicates via complementary base pairing (A-T, C-G). During transcription, RNA polymerase synthesizes messenger RNA (mRNA) from DNA templates, which ribosomes translate into amino acid protein sequences.",
        "DNA double helix structure, transcription, and translation biology",
    )

    add(
        "sem_wk_004",
        "Macroeconomics examines economy-wide phenomena such as inflation, price levels, rate of economic growth, national income, gross domestic product (GDP), and changes in unemployment. Monetary policy, executed by central banks, manages interest rates and money supply to maintain price stability and full employment. Fiscal policy, determined by legislative governments, utilizes taxation and government spending to stimulate aggregate demand during economic recessions or cool down inflationary overheating.",
        "Macroeconomics fundamentals (Monetary and fiscal policy, GDP)",
    )

    add(
        "sem_wk_005",
        "Plate tectonics is the unifying geological theory explaining the large-scale motion of seven major and numerous minor lithospheric plates floating upon the ductile asthenosphere mantle. Plate boundaries are classified into three types: Divergent boundaries (where plates pull apart, forming mid-ocean ridges and rift valleys), Convergent boundaries (where plates collide, causing subduction zones, volcanic mountain ranges, and deep oceanic trenches), and Transform boundaries (where plates slide horizontally past one another, generating frequent earthquakes along strike-slip fault lines like the San Andreas Fault).",
        "Plate tectonics, continental drift, and earthquake geology",
    )

    add(
        "sem_wk_006",
        "Thermodynamics is the branch of physical chemistry governing energy transformations and heat transfer. The First Law of Thermodynamics (Conservation of Energy) states that energy cannot be created or destroyed, only altered in form. The Second Law of Thermodynamics introduces the concept of Entropy, establishing that the total entropy of an isolated system always increases over time, dictating the thermodynamic arrow of time and the impossibility of constructing a 100% efficient perpetual motion engine.",
        "First and Second Laws of Thermodynamics and entropy",
    )

    add(
        "sem_wk_007",
        "Cellular respiration is the metabolic pathway through which biological cells convert biochemical energy from nutrients (such as glucose) into adenosine triphosphate (ATP), releasing carbon dioxide and water as byproducts. The aerobic respiration pathway comprises three sequential stages: Glycolysis in the cytoplasm (breaking glucose into pyruvate), the Krebs Cycle (Citric Acid Cycle) in the mitochondrial matrix (generating electron carriers NADH and FADH2), and Oxidative Phosphorylation along the mitochondrial inner membrane (using the electron transport chain and ATP synthase to generate up to 36-38 ATP molecules per glucose).",
        "Cellular respiration stages (Glycolysis, Krebs cycle, Oxidative phosphorylation)",
    )

    add(
        "sem_wk_008",
        "The Industrial Revolution, beginning in Great Britain in the mid-18th century, marked a historic transition from agrarian, handicraft economies to machine-driven industrial manufacturing. Key catalysts included the development of James Watt's efficient steam engine, mechanized textile manufacturing with the spinning jenny and power loom, the expansion of iron metallurgy using coke smelting, and the construction of extensive canal and railway networks. This transformation drove rapid urbanization, established factory wage labor systems, and catalyzed the emergence of modern capitalism.",
        "Industrial Revolution technological and socioeconomic transformation",
    )

    add(
        "sem_wk_009",
        "Game Theory is the formal mathematical study of strategic interaction among rational decision-makers. In non-cooperative game theory, the Nash Equilibrium defines a state where no player has an incentive to unilaterally deviate from their chosen strategy given the strategies of all other participants. Classic games like the Prisoner's Dilemma illustrate how individual rationality can lead to collectively suboptimal outcomes, providing critical insights for economics, evolutionary biology, cybersecurity protocol design, and distributed multi-agent consensus systems.",
        "Game Theory, Nash Equilibrium, and Prisoner's Dilemma in systems design",
    )

    add(
        "sem_wk_010",
        "Photosynthesis is the fundamental photochemical process by which green plants, algae, and cyanobacteria convert solar light energy into chemical energy stored in glucose carbohydrate molecules. Occurring within specialized cellular organelles called Chloroplasts, photosynthesis consists of Light-Dependent Reactions (wherein chlorophyll pigments absorb photons, photolyze water molecules into oxygen and hydrogen ions, and synthesize ATP and NADPH) and the Light-Independent Calvin Cycle (wherein the enzyme RuBisCO fixes atmospheric carbon dioxide into high-energy sugars).",
        "Photosynthesis photochemistry, Chloroplasts, and the Calvin Cycle",
    )

    return samples
