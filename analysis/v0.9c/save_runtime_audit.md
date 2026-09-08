# Save and PC runtime audit

Frozen ROM replay: 14 explicit controller routes, 134/134 recorded screens identical. Fresh new game reaches the first save without RAM intervention; two cold starts reload it. Default compact record bytes preserve 훌리오 and 캐로. Mixed six-cell and legacy-name samples are saved and cold-loaded; raw party record hashes are retained in runtime_summary.json. The legacy test is a known converted local sample, not a claim that any unmodified Japanese/BETA2 save will import automatically.

Item and 필리아's inspection arte both show legible enemy name, HP, race, strengths and weaknesses; item window and arte window were visually inspected on the rerun. Their routes use one isolated RAM setup each; windows open and close through actual battle controls. A separate battle route uses no RAM writes. Suspend save→cold resume→consumed-menu behaviour is reproduced and the resumed field screen inspected.

Frozen EEPROM bytes match BETA3/Japanese. PC tests do not establish SD/flashcart power-loss durability, actual console timing or two-device exchange. No cross-ROM savestate was used, and input saves were copied into core memory only. Original save files remain private and are not uploaded. Candidate-file runtime results are recorded separately after clean builds.
