---
title: "Power-consumption Backdoor in Quantum Key Distribution"
collection: publications
permalink: /publication/costa_2025_powerconsumption_backdoor_in
excerpt: 'Over the last decades, Quantum Key Distribution (QKD) has risen as a promising solution for secure communications. However, like all cryptographic protocols, QKD implementations can open security vuln...' if len(self.abstract) > 200 else self.abstract
date: 2025-01-01
venue: 'Physical Review Applied'
paperurl: 'https://doi.org/10.1103/f92x-c3zj'
citation: 'Beatriz Lopes da Costa, Matías R. Bolaños, Ricardo Chaves, Claudio Narduzzi, Marco Avesani, David..., "Power-consumption Backdoor in Quantum Key Distribution", Physical Review Applied, (2025).'
---

Over the last decades, Quantum Key Distribution (QKD) has risen as a promising solution for secure communications. However, like all cryptographic protocols, QKD implementations can open security vulnerabilities. Until now, the study of physical vulnerabilities in QKD setups has primarily focused on the optical channel. In classical cryptoanalysis, power and electromagnetic side-channel analysis are powerful techniques used to access unwanted information about the encryption key in symmetric-key algorithms. In QKD they have rarely been used, since they require an eavesdropper to have access to Alice or Bob's setups. However, security proofs of QKD protocols generally assume that these setups are secure, making it crucial to understand the necessary security measures to ensure this protection. In this work, we propose and implement a power side-channel analysis to a QKD system, by exploiting the power consumption of the electronic driver controlling the electro-optical components of the QKD transmitter. QKD modules typically require very precise electronic drivers, such as Field Programmable Gate Arrays (FPGAs). Here, we show that the FPGA's power consumption can leak information about the QKD operation, and consequently the transmitted key. The analysis was performed on the QKD transmitter at the University of Padua. Our results are consistent and show critical information leakage, having reached a maximum accuracy of 73.35% in predicting transmitted qubits at a 100 MHz repetition frequency.

**Authors:** Beatriz Lopes da Costa, Matías R. Bolaños, Ricardo Chaves, Claudio Narduzzi, **Marco Avesani**, Davide Giacomo Marangon, Andrea Stanco, Giuseppe Vallone, Paolo Villoresi, Yasser Omar


[Journal](https://doi.org/10.1103/f92x-c3zj){: .btn .btn--info} [ArXiv](https://arxiv.org/abs/2503.11767){: .btn .btn--info}
