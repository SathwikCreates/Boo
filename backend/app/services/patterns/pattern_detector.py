import asyncio
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from collections import Counter, defaultdict
import re
import json
import time
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import silhouette_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.db.database import get_db
from app.services.embedding_service import EmbeddingService
from app.services.ollama.ollama_service import OllamaService
from app.db.repositories.preferences_repository import PreferencesRepository
from app.core.config import settings
from .pattern_types import Pattern, PatternType


class PatternDetector:
    """Service for detecting patterns in journal entries"""
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.ollama_service = OllamaService()
        self.min_cluster_size = 1  # Minimum entries to form a pattern
        self.similarity_threshold = 0.5  # Cosine similarity threshold (lowered for more distinct clusters)
        
    async def analyze_entries(self, min_entries: int = 1) -> List[Pattern]:
        """Analyze all entries and detect patterns"""
        # Fetch all entries with embeddings
        entries = await self._fetch_entries_with_embeddings()
        if not entries:
            return []
            
        patterns = []
        
        # Detect topic patterns using embeddings
        topic_patterns = await self._detect_topic_patterns(entries)
        patterns.extend(topic_patterns)
        
        # Detect mood patterns
        mood_patterns = await self._detect_mood_patterns(entries)
        patterns.extend(mood_patterns)
        
        # Detect temporal patterns
        temporal_patterns = await self._detect_temporal_patterns(entries)
        patterns.extend(temporal_patterns)
        
        # Store patterns in database
        await self._store_patterns(patterns)
        
        return patterns
    
    async def _get_entry_count(self) -> int:
        """Get total number of entries"""
        db = get_db()
        result = await db.fetch_one("SELECT COUNT(*) as count FROM entries")
        return result["count"] if result else 0
    
    async def _fetch_entries_with_embeddings(self) -> List[Dict]:
        """Fetch all entries that have embeddings"""
        db = get_db()
        query = """
            SELECT id, raw_text, enhanced_text, structured_summary, 
                   embeddings, timestamp, mood_tags
            FROM entries 
            WHERE embeddings IS NOT NULL
            ORDER BY timestamp DESC
        """
        rows = await db.fetch_all(query)
        
        entries = []
        for row in rows:
            entry = dict(row)
            # Parse embeddings from JSON
            if entry["embeddings"]:
                entry["embeddings"] = json.loads(entry["embeddings"])
            # Parse mood tags
            if entry["mood_tags"]:
                entry["mood_tags"] = json.loads(entry["mood_tags"])
            else:
                entry["mood_tags"] = []
            # Parse timestamp to datetime object
            if isinstance(entry["timestamp"], str):
                entry["timestamp"] = datetime.fromisoformat(entry["timestamp"])
            entries.append(entry)
            
        return entries
    
    async def _detect_topic_patterns(self, entries: List[Dict]) -> List[Pattern]:
        """Detect topic patterns using embeddings and clustering"""
        if len(entries) < self.min_cluster_size:
            return []
            
        try:
            # Extract embeddings and create a mapping to valid entries
            embeddings_list = []
            valid_entries = []
            for entry in entries:
                if entry["embeddings"] and len(entry["embeddings"]) > 0:
                    embeddings_list.append(entry["embeddings"])
                    valid_entries.append(entry)
            
            if len(embeddings_list) < self.min_cluster_size:
                return []
                
            embeddings = np.array(embeddings_list)
            
            # Try multiple clustering approaches to find distinct patterns
            best_clustering = None
            best_num_clusters = 0
            
            # Try different eps values to find optimal clustering
            eps_values = [0.4, 0.5, 0.6, 0.7, 0.8]
            
            for eps in eps_values:
                clustering = DBSCAN(
                    eps=eps,
                    min_samples=self.min_cluster_size,
                    metric='cosine'
                ).fit(embeddings)
                
                # Count valid clusters (ignore noise cluster -1)
                unique_labels = set(clustering.labels_)
                num_clusters = len([label for label in unique_labels if label != -1])
                
                # Count entries in each cluster
                cluster_sizes = {}
                for label in clustering.labels_:
                    if label != -1:
                        cluster_sizes[label] = cluster_sizes.get(label, 0) + 1
                
                print(f"DBSCAN eps={eps}: {num_clusters} clusters, sizes: {list(cluster_sizes.values())}")
                
                # Prefer clustering with 2-6 distinct clusters
                if 2 <= num_clusters <= 6 and num_clusters > best_num_clusters:
                    best_clustering = clustering
                    best_num_clusters = num_clusters
            
            # If no good clustering found, try K-means with silhouette optimization
            if best_clustering is None:
                print("DBSCAN failed to find good clusters, trying K-means with silhouette optimization...")
                
                best_kmeans = None
                best_silhouette = -1
                max_k = min(10, len(valid_entries) // self.min_cluster_size + 1)
                
                for k in range(2, max_k):
                    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10).fit(embeddings)
                    
                    # Check if all clusters meet minimum size requirement
                    cluster_sizes = {}
                    for label in kmeans.labels_:
                        cluster_sizes[label] = cluster_sizes.get(label, 0) + 1
                    
                    min_size = min(cluster_sizes.values())
                    if min_size >= self.min_cluster_size:
                        # Calculate silhouette score for this clustering
                        silhouette = silhouette_score(embeddings, kmeans.labels_)
                        print(f"K-means k={k}: silhouette={silhouette:.3f}, cluster sizes: {list(cluster_sizes.values())}")
                        
                        if silhouette > best_silhouette:
                            best_kmeans = kmeans
                            best_silhouette = silhouette
                
                if best_kmeans is not None:
                    clustering = best_kmeans
                    print(f"Selected optimal clustering with silhouette score: {best_silhouette:.3f}")
                else:
                    # Last resort: use simple DBSCAN
                    clustering = DBSCAN(
                        eps=0.5,
                        min_samples=self.min_cluster_size,
                        metric='cosine'
                    ).fit(embeddings)
            else:
                clustering = best_clustering
            
        except Exception as e:
            return []
        
        # Group entries by cluster
        clusters = defaultdict(list)
        for idx, label in enumerate(clustering.labels_):
            if label != -1:  # Ignore noise points
                clusters[label].append(idx)
        
        patterns = []
        for cluster_id, entry_indices in clusters.items():
            if len(entry_indices) >= self.min_cluster_size:
                # Extract entries in this cluster
                cluster_entries = [valid_entries[i] for i in entry_indices]
                
                # Skip if cluster is too large (likely everything got grouped together)
                if len(cluster_entries) > len(valid_entries) * 0.7:
                    continue
                
                # Generate pattern description using LLM
                pattern_desc = await self._generate_pattern_description(
                    cluster_entries, PatternType.TOPIC
                )
                
                # Extract keywords using TF-IDF
                keywords = self._extract_keywords(cluster_entries)
                
                # Create pattern
                pattern = Pattern(
                    pattern_type=PatternType.TOPIC,
                    description=pattern_desc,
                    frequency=len(cluster_entries),
                    confidence=self._calculate_cluster_confidence(
                        embeddings[entry_indices]
                    ),
                    first_seen=min(e["timestamp"] for e in cluster_entries),
                    last_seen=max(e["timestamp"] for e in cluster_entries),
                    related_entries=[e["id"] for e in cluster_entries],
                    keywords=keywords[:10]  # Top 10 keywords
                )
                patterns.append(pattern)
                
        return patterns
    
    async def _detect_mood_patterns(self, entries: List[Dict]) -> List[Pattern]:
        """Detect mood patterns from mood tags"""
        mood_counter = Counter()
        mood_entries = defaultdict(list)
        
        for entry in entries:
            if entry["mood_tags"]:
                for mood in entry["mood_tags"]:
                    mood_counter[mood] += 1
                    mood_entries[mood].append(entry)
        
        patterns = []
        for mood, count in mood_counter.most_common():
            if count >= self.min_cluster_size:
                related_entries = mood_entries[mood]
                
                pattern = Pattern(
                    pattern_type=PatternType.MOOD,
                    description=f"Frequent mood: {mood}",
                    frequency=count,
                    confidence=count / len(entries),  # Proportion of entries with this mood
                    first_seen=min(e["timestamp"] for e in related_entries),
                    last_seen=max(e["timestamp"] for e in related_entries),
                    related_entries=[e["id"] for e in related_entries],
                    keywords=[mood]
                )
                patterns.append(pattern)
                
        return patterns
    
    async def _detect_temporal_patterns(self, entries: List[Dict]) -> List[Pattern]:
        """Detect temporal patterns (e.g., time of day, day of week)"""
        time_patterns = defaultdict(list)
        day_patterns = defaultdict(list)
        
        for entry in entries:
            timestamp = entry["timestamp"]
            # Ensure timestamp is a datetime object
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            # Time of day pattern
            hour = timestamp.hour
            if 5 <= hour < 12:
                time_period = "morning"
            elif 12 <= hour < 17:
                time_period = "afternoon"
            elif 17 <= hour < 22:
                time_period = "evening"
            else:
                time_period = "night"
            time_patterns[time_period].append(entry)
            
            # Day of week pattern
            day_name = timestamp.strftime("%A")
            day_patterns[day_name].append(entry)
        
        patterns = []
        
        # Process time patterns
        for period, period_entries in time_patterns.items():
            if len(period_entries) >= self.min_cluster_size:
                pattern = Pattern(
                    pattern_type=PatternType.TEMPORAL,
                    description=f"Frequent journaling in the {period}",
                    frequency=len(period_entries),
                    confidence=len(period_entries) / len(entries),
                    first_seen=min(e["timestamp"] for e in period_entries),
                    last_seen=max(e["timestamp"] for e in period_entries),
                    related_entries=[e["id"] for e in period_entries],
                    keywords=[period, "time"]
                )
                patterns.append(pattern)
        
        # Process day patterns
        for day, day_entries in day_patterns.items():
            if len(day_entries) >= self.min_cluster_size:
                pattern = Pattern(
                    pattern_type=PatternType.TEMPORAL,
                    description=f"Frequent journaling on {day}s",
                    frequency=len(day_entries),
                    confidence=len(day_entries) / len(entries),
                    first_seen=min(e["timestamp"] for e in day_entries),
                    last_seen=max(e["timestamp"] for e in day_entries),
                    related_entries=[e["id"] for e in day_entries],
                    keywords=[day, "weekday"]
                )
                patterns.append(pattern)
                
        return patterns
    
    async def _generate_pattern_description(
        self, entries: List[Dict], pattern_type: PatternType
    ) -> str:
        """Generate a human-readable description of the pattern using LLM"""
        # Sample a few entries for the prompt
        sample_size = min(5, len(entries))
        sample_entries = entries[:sample_size]
        
        # Prepare text samples
        text_samples = []
        for entry in sample_entries:
            text = entry.get("structured_summary") or entry.get("enhanced_text") or entry["raw_text"]
            # Limit text length
            text = text[:200] + "..." if len(text) > 200 else text
            text_samples.append(text)
        
        prompt = f"""Analyze these journal entry samples and identify the SPECIFIC common theme or pattern:

{chr(10).join(f'{i+1}. {text}' for i, text in enumerate(text_samples))}

Create a specific, descriptive title for this topic pattern. Examples:
- "Work stress and deadline pressure"
- "Family relationships and communication"
- "Health and fitness goals"
- "Travel and adventure experiences"
- "Creative projects and artistic pursuits"

Respond with only the specific topic title (max 8 words). Be precise, not generic."""

        try:
            # Get model and settings from preferences
            model = await PreferencesRepository.get_value('ollama_model', settings.OLLAMA_DEFAULT_MODEL)
            temperature = await PreferencesRepository.get_value('ollama_temperature', 0.3)
            context_window = await PreferencesRepository.get_value('ollama_context_window', 4096)
            
            response = await self.ollama_service.generate(
                prompt=prompt,
                model=model,
                options={
                    'temperature': temperature,
                    'num_ctx': context_window,
                    'num_gpu': -1  # Use all GPU layers for maximum performance
                }
            )
            
            if response and response.response:
                # Clean and truncate the response
                description = response.response.strip()
                # Remove quotes if present
                description = description.strip('"\'')
                # Ensure it's not too long
                words = description.split()
                if len(words) > 10:
                    description = " ".join(words[:10]) + "..."
                return description
            else:
                return "Common theme detected"
                
        except Exception as e:
            return "Common theme detected"
    
    def _extract_keywords(self, entries: List[Dict], max_keywords: int = 20) -> List[str]:
        """Extract keywords from entries using TF-IDF"""
        # Combine all text from entries
        texts = []
        for entry in entries:
            text = entry.get("structured_summary") or entry.get("enhanced_text") or entry["raw_text"]
            texts.append(text)
        
        if not texts:
            return []
        
        try:
            # Use TF-IDF to extract important terms
            vectorizer = TfidfVectorizer(
                max_features=max_keywords * 2,  # Get more candidates
                stop_words='english',
                ngram_range=(1, 2),  # Include bigrams
                min_df=1,  # Allow single occurrences for smaller clusters
                max_df=0.8  # Ignore terms that appear in >80% of documents
            )
            
            tfidf_matrix = vectorizer.fit_transform(texts)
            feature_names = vectorizer.get_feature_names_out()
            
            # Get average TF-IDF scores across all documents
            avg_scores = tfidf_matrix.mean(axis=0).A1
            
            # Sort by score
            sorted_indices = avg_scores.argsort()[::-1]
            
            # Extract top keywords
            keywords = [feature_names[i] for i in sorted_indices[:max_keywords]]
            
            return keywords
            
        except Exception as e:
            print(f"Error extracting keywords: {e}")
            return []
    
    def _calculate_cluster_confidence(self, embeddings: np.ndarray) -> float:
        """Calculate confidence score for a cluster based on cohesion"""
        if len(embeddings) < 2:
            return 1.0
            
        # Calculate pairwise similarities
        similarities = cosine_similarity(embeddings)
        
        # Get average similarity (excluding diagonal)
        n = len(embeddings)
        total_sim = (similarities.sum() - n) / (n * (n - 1))
        
        return float(total_sim)
    
    async def _store_patterns(self, patterns: List[Pattern]) -> None:
        """Store patterns in the database"""
        db = get_db()
        try:
            # Clear existing patterns and insert new ones in a transaction
            await db.execute("DELETE FROM patterns")
            
            # Insert new patterns
            for pattern in patterns:
                data = pattern.to_dict()
                await db.execute(
                    """INSERT INTO patterns 
                       (pattern_type, description, frequency, confidence, 
                        first_seen, last_seen, related_entries, keywords)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        data["pattern_type"],
                        data["description"],
                        data["frequency"],
                        data["confidence"],
                        data["first_seen"],
                        data["last_seen"],
                        data["related_entries"],
                        data["keywords"]
                    )
                )
            
            await db.commit()
            
        except Exception as e:
            # Rollback transaction to release any database locks
            try:
                await db.rollback()
            except Exception as rollback_error:
                # If rollback fails, log it but don't mask the original error
                pass
            
            # Re-raise the original exception with context
            raise Exception(f"Failed to store patterns: {str(e)}")
    
    async def get_patterns(self) -> List[Pattern]:
        """Get all stored patterns from database"""
        db = get_db()
        rows = await db.fetch_all(
            "SELECT * FROM patterns ORDER BY frequency DESC, confidence DESC"
        )
        
        patterns = []
        for row in rows:
            row_dict = dict(row)
            # Ensure keywords field exists
            if 'keywords' not in row_dict:
                row_dict['keywords'] = "[]"
            pattern = Pattern.from_dict(row_dict)
            patterns.append(pattern)
            
        return patterns
    
