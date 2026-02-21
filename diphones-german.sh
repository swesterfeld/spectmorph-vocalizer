cat diphones-german-possible.txt diphones-german-hiatus-possible.txt diphones-german-non-released-plosives.txt > diphones-german-all.txt
diphone-checker.py gen-script diphones-german-all.txt dict-neu |& tee diphones-german-all.log

