#!/usr/bin/env python3
"""
[EXPERIMENTAL PROTOTYPE]
Contrastive Ranking Trainer for grepai
Trains a prototype neural re-ranking model using Margin Ranking Loss on
(anchor: query, positive: true_code, negative: hard_distractor) triplets collected via telemetry.
Note: In production, Stage 2 re-ranking uses local LLMs in LM Studio via semcode.pipeline.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset


class TripletDataset(Dataset):
    """Dataset for query-positive-negative code triplets."""
    def __init__(self, triplets: List[Dict[str, str]], vocab: Dict[str, int], max_len: int = 256):
        self.triplets = triplets
        self.vocab = vocab
        self.max_len = max_len

    def __len__(self):
        return len(self.triplets)

    def tokenize(self, text: str) -> torch.Tensor:
        words = text.lower().split()[:self.max_len]
        tokens = [self.vocab.get(w, 1) for w in words]  # 1 = <unk>
        if len(tokens) < self.max_len:
            tokens.extend([0] * (self.max_len - len(tokens)))  # 0 = <pad>
        return torch.tensor(tokens, dtype=torch.long)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        t = self.triplets[idx]
        anc = self.tokenize(t["anchor"])
        pos = self.tokenize(t["positive"])
        neg = self.tokenize(t["negative"])
        return anc, pos, neg


class CodeReRankerModel(nn.Module):
    """
    Lightweight Neural Cross-Score Re-Ranker.
    Computes contrastive matching score between query and candidate code snippet.
    """
    def __init__(self, vocab_size: int, embed_dim: int = 128, hidden_dim: int = 256):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.encoder = nn.GRU(embed_dim, hidden_dim, batch_first=True, bidirectional=True)
        self.scorer = nn.Sequential(
            nn.Linear(hidden_dim * 4, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 1)
        )

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        embedded = self.embedding(x)
        out, _ = self.encoder(embedded)
        # Mean pooling over sequence length
        pooled = torch.mean(out, dim=1)
        return pooled

    def score_pair(self, q_repr: torch.Tensor, c_repr: torch.Tensor) -> torch.Tensor:
        # Combined feature representation: [q, c, |q - c|, q * c]
        combined = torch.cat([q_repr, c_repr], dim=1)
        return self.scorer(combined).squeeze(-1)

    def forward(self, anchor: torch.Tensor, positive: torch.Tensor, negative: torch.Tensor):
        q_repr = self.encode(anchor)
        pos_repr = self.encode(positive)
        neg_repr = self.encode(negative)

        pos_score = self.score_pair(q_repr, pos_repr)
        neg_score = self.score_pair(q_repr, neg_repr)
        return pos_score, neg_score


def build_vocab(triplets: List[Dict[str, str]], max_vocab: int = 10000) -> Dict[str, int]:
    word_counts = {}
    for t in triplets:
        for key in ["anchor", "positive", "negative"]:
            for w in t[key].lower().split():
                word_counts[w] = word_counts.get(w, 0) + 1

    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:max_vocab]
    vocab = {"<pad>": 0, "<unk>": 1}
    for idx, (w, _) in enumerate(sorted_words, 2):
        vocab[w] = idx
    return vocab


def generate_synthetic_triplets(num_samples: int = 30) -> List[Dict[str, str]]:
    """Generates mock training triplets for verification if telemetry is small."""
    triplets = []
    topics = [
        ("retry exponential delay jitter", "func RetryWithBackoff(ctx, maxAttempts, initialInterval)", "func ParseTimeoutOption(v string) error"),
        ("throttle quota limit token bucket", "type RateLimiter struct { tokens int; capacity int }", "func TestRateLimiterMock(t *testing.T)"),
        ("parse abstract syntax tree", "func ParseAST(code []byte, lang string) (*Tree, error)", "func FormatCLIError(err error) string"),
        ("calculate cosine similarity vector", "func CosineSimilarity(a, b []float32) float32", "func LogHTTPRequest(method, path string)"),
        ("filter gitignore disk artifacts", "func MatchGitignore(path string, patterns []string) bool", "func ReadConfigFile(path string) (*Config, error)")
    ]
    for i in range(num_samples):
        topic = topics[i % len(topics)]
        triplets.append({
            "anchor": f"{topic[0]} sample {i}",
            "positive": f"{topic[1]} // implementation body {i}",
            "negative": f"{topic[2]} // distractor body {i}"
        })
    return triplets


def train(
    triplets: List[Dict[str, str]],
    epochs: int = 5,
    batch_size: int = 8,
    lr: float = 1e-3,
    margin: float = 0.5,
    checkpoint_dir: str = "training/checkpoints"
) -> Dict[str, Any]:
    print(f"\nBuilding vocabulary from {len(triplets)} training triplets...")
    vocab = build_vocab(triplets)
    print(f"Vocabulary size: {len(vocab)}")

    dataset = TripletDataset(triplets, vocab)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on device: {device}")

    model = CodeReRankerModel(vocab_size=len(vocab)).to(device)
    criterion = nn.MarginRankingLoss(margin=margin)
    optimizer = optim.AdamW(model.parameters(), lr=lr)

    model.train()
    history = []

    print("\nStarting Contrastive Training...")
    for epoch in range(1, epochs + 1):
        epoch_loss = 0.0
        correct_pairs = 0
        total_pairs = 0

        for anchor, pos, neg in dataloader:
            anchor = anchor.to(device)
            pos = pos.to(device)
            neg = neg.to(device)

            optimizer.zero_grad()
            pos_score, neg_score = model(anchor, pos, neg)

            # Target is 1: pos_score should be greater than neg_score
            target = torch.ones_like(pos_score)
            loss = criterion(pos_score, neg_score, target)

            loss.backward()
            optimizer.step()

            epoch_loss += loss.item() * anchor.size(0)
            correct_pairs += (pos_score > neg_score).sum().item()
            total_pairs += anchor.size(0)

        avg_loss = epoch_loss / total_pairs
        accuracy = correct_pairs / total_pairs * 100.0
        history.append({"epoch": epoch, "loss": avg_loss, "accuracy": accuracy})
        print(f"  Epoch [{epoch:02d}/{epochs:02d}] - Loss: {avg_loss:.4f} | Pair Accuracy: {accuracy:.1f}%")

    out_dir = Path(checkpoint_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    weights_path = out_dir / "reranker_weights.pt"
    vocab_path = out_dir / "vocab.json"

    torch.save(model.state_dict(), weights_path)
    with open(vocab_path, "w", encoding="utf-8") as f:
        json.dump(vocab, f)

    print(f"\n[SUCCESS] Model checkpoint saved to: {weights_path}")
    print(f"Vocabulary metadata saved to: {vocab_path}")
    return {"final_loss": avg_loss, "final_accuracy": accuracy, "checkpoint": str(weights_path)}


def main():
    parser = argparse.ArgumentParser(description="Contrastive Ranking Trainer for grepai")
    parser.add_argument("--triplets", type=str, default="telemetry/triplets.jsonl", help="Path to triplets JSONL")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--margin", type=float, default=0.5, help="Margin for MarginRankingLoss")
    parser.add_argument("--dry-run", action="store_true", help="Train on synthetic triplets for verification")
    args = parser.parse_args()

    triplets = []
    if not args.dry_run and os.path.isfile(args.triplets):
        with open(args.triplets, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    triplets.append(json.loads(line))

    if len(triplets) < 5 or args.dry_run:
        print(f"Using {30} synthetic triplets for demonstration/verification...")
        triplets = generate_synthetic_triplets(30)

    train(
        triplets=triplets,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        margin=args.margin
    )


if __name__ == "__main__":
    main()
