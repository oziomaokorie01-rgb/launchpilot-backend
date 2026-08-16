from datetime import datetime
import os
import uuid

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker


load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

DATABASE_URL = "sqlite:///./launchpilot.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class AppModel(Base):
    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    url = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    audience = Column(String(300), nullable=False)
    goal = Column(String(300), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CampaignModel(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    channel = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    tracking_code = Column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow)


class ClickModel(Base):
    __tablename__ = "clicks"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(
        Integer,
        ForeignKey("campaigns.id"),
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow)


class MissionModel(Base):
    __tablename__ = "missions"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)

    order_number = Column(Integer, nullable=False)
    mission_type = Column(String(50), nullable=False)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)

    target = Column(Integer, default=1)
    progress = Column(Integer, default=0)

    status = Column(String(50), default="pending")
    completed = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)


class OpportunityModel(Base):
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)

    opportunity_type = Column(String(50), nullable=False)
    platform = Column(String(80), nullable=False)

    name = Column(String(200), nullable=False)
    url = Column(String(500), nullable=True)

    audience = Column(String(300), nullable=True)
    description = Column(Text, nullable=True)

    relevance_score = Column(Integer, default=0)

    why_match = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=True)

    status = Column(String(50), default="new")
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


class AppCreate(BaseModel):
    name: str
    url: str
    description: str
    audience: str
    goal: str


app = FastAPI(title="LaunchPilot API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
	"https://rj82zr9qagllr85ruo4ez3yvkrp61f8jlbj9ejug.hackonvibe.com",
  
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "name": "LaunchPilot API",
        "status": "online",
    }


@app.post("/api/apps")
def create_app(payload: AppCreate):
    db = SessionLocal()

    try:
        new_app = AppModel(
            name=payload.name,
            url=payload.url,
            description=payload.description,
            audience=payload.audience,
            goal=payload.goal,
        )

        db.add(new_app)
        db.commit()
        db.refresh(new_app)

        return {
            "id": new_app.id,
            "name": new_app.name,
            "url": new_app.url,
            "description": new_app.description,
            "audience": new_app.audience,
            "goal": new_app.goal,
            "created_at": new_app.created_at,
        }

    finally:
        db.close()


@app.get("/r/{tracking_code}")
def track_click(tracking_code: str):
    db = SessionLocal()

    try:
        campaign = (
            db.query(CampaignModel)
            .filter(CampaignModel.tracking_code == tracking_code)
            .first()
        )

        if not campaign:
            raise HTTPException(
                status_code=404,
                detail="Tracking link not found",
            )

        app_record = (
            db.query(AppModel)
            .filter(AppModel.id == campaign.app_id)
            .first()
        )

        if not app_record:
            raise HTTPException(
                status_code=404,
                detail="App not found",
            )

        click = ClickModel(campaign_id=campaign.id)

        db.add(click)
        db.commit()

        return RedirectResponse(
            url=app_record.url,
            status_code=302,
        )

    finally:
        db.close()


@app.get("/api/apps/{app_id}/analytics")
def get_analytics(app_id: int):
    db = SessionLocal()

    try:
        app_record = (
            db.query(AppModel)
            .filter(AppModel.id == app_id)
            .first()
        )

        if not app_record:
            raise HTTPException(
                status_code=404,
                detail="App not found",
            )

        campaigns = (
            db.query(CampaignModel)
            .filter(CampaignModel.app_id == app_id)
            .all()
        )

        results = []

        for campaign in campaigns:
            click_count = (
                db.query(ClickModel)
                .filter(ClickModel.campaign_id == campaign.id)
                .count()
            )

            results.append(
                {
                    "campaign_id": campaign.id,
                    "channel": campaign.channel,
                    "title": campaign.title,
                    "tracking_code": campaign.tracking_code,
                    "clicks": click_count,
                }
            )

        return {
            "app_id": app_record.id,
            "app_name": app_record.name,
            "campaigns": results,
        }

    finally:
        db.close()


@app.post("/api/apps/{app_id}/roadmap")
def create_roadmap(app_id: int):
    db = SessionLocal()

    try:
        app_record = (
            db.query(AppModel)
            .filter(AppModel.id == app_id)
            .first()
        )

        if not app_record:
            raise HTTPException(
                status_code=404,
                detail="App not found",
            )

        existing_missions = (
            db.query(MissionModel)
            .filter(MissionModel.app_id == app_id)
            .order_by(MissionModel.order_number)
            .all()
        )

        if existing_missions:
            return {
                "app_id": app_record.id,
                "app_name": app_record.name,
                "goal": app_record.goal,
                "missions": [
                    {
                        "id": mission.id,
                        "order": mission.order_number,
                        "type": mission.mission_type,
                        "title": mission.title,
                        "description": mission.description,
                        "target": mission.target,
                        "progress": mission.progress,
                        "status": mission.status,
                        "completed": mission.completed,
                    }
                    for mission in existing_missions
                ],
            }

        roadmap = [
            {
                "order": 1,
                "type": "campaign",
                "title": "Test your message",
                "description": (
                    "Test different promotional messages and learn "
                    "which positioning attracts the most interest."
                ),
                "target": 3,
            },
            {
                "order": 2,
                "type": "users",
                "title": "Reach your first users",
                "description": (
                    f"Find and reach people matching the core audience: "
                    f"{app_record.audience}."
                ),
                "target": 20,
            },
            {
                "order": 3,
                "type": "communities",
                "title": "Find relevant communities",
                "description": (
                    "Identify communities where your target users "
                    "already gather and discuss their problems."
                ),
                "target": 5,
            },
            {
                "order": 4,
                "type": "creators",
                "title": "Contact relevant creators",
                "description": (
                    "Find creators whose audiences overlap with "
                    "your target users and prepare personalized outreach."
                ),
                "target": 10,
            },
            {
                "order": 5,
                "type": "partners",
                "title": "Find distribution partners",
                "description": (
                    "Identify complementary founders, products, "
                    "newsletters and organizations that reach the same audience."
                ),
                "target": 5,
            },
            {
                "order": 6,
                "type": "analysis",
                "title": "Analyse what worked",
                "description": (
                    "Compare traffic across campaigns and distribution "
                    "channels to identify the strongest acquisition route."
                ),
                "target": 1,
            },
            {
                "order": 7,
                "type": "optimize",
                "title": "Double down on winners",
                "description": (
                    "Use the strongest results to decide the next "
                    "promotion action."
                ),
                "target": 1,
            },
        ]

        created_missions = []

        for item in roadmap:
            mission = MissionModel(
                app_id=app_record.id,
                order_number=item["order"],
                mission_type=item["type"],
                title=item["title"],
                description=item["description"],
                target=item["target"],
            )

            db.add(mission)
            db.flush()

            created_missions.append(
                {
                    "id": mission.id,
                    "order": mission.order_number,
                    "type": mission.mission_type,
                    "title": mission.title,
                    "description": mission.description,
                    "target": mission.target,
                    "progress": mission.progress,
                    "status": mission.status,
                    "completed": mission.completed,
                }
            )

        db.commit()

        return {
            "app_id": app_record.id,
            "app_name": app_record.name,
            "goal": app_record.goal,
            "missions": created_missions,
        }

    finally:
        db.close()


def get_youtube_channel_details(channel_ids: list[str]):
    if not channel_ids:
        return {}

    response = httpx.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={
            "part": "snippet,statistics",
            "id": ",".join(channel_ids),
            "key": YOUTUBE_API_KEY,
        },
        timeout=20.0,
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"YouTube channel API error: {response.text}",
        )

    channels = {}

    for item in response.json().get("items", []):
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})

        channels[item["id"]] = {
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "subscriber_count": int(stats.get("subscriberCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
            "view_count": int(stats.get("viewCount", 0)),
            "hidden_subscribers": stats.get("hiddenSubscriberCount", False),
        }

    return channels


def score_creator(
    creator: dict,
    channel_details: dict,
    audience: str,
):
    text = (
        f"{creator['name']} "
        f"{channel_details.get('description', '')}"
    ).lower()

    score = 40
    reasons = []

    strong_keywords = [
        "university",
        "college",
        "student",
        "study",
        "studying",
        "exam",
        "revision",
        "productivity",
        "learning",
    ]

    keyword_matches = [
        keyword
        for keyword in strong_keywords
        if keyword in text
    ]

    score += min(len(keyword_matches) * 6, 30)

    if keyword_matches:
        reasons.append(
            "Relevant topics: "
            + ", ".join(keyword_matches[:4])
        )

    if creator["matches"] > 1:
        score += min(creator["matches"] * 4, 12)
        reasons.append(
            f"Appeared in {creator['matches']} relevant searches"
        )

    subscribers = channel_details.get("subscriber_count", 0)
    videos = channel_details.get("video_count", 0)

    if 1_000 <= subscribers <= 100_000:
        score += 15
        reasons.append(
            "Micro/mid-size creator with realistic outreach potential"
        )
    elif 100_001 <= subscribers <= 500_000:
        score += 10
        reasons.append(
            "Established creator with strong potential reach"
        )
    elif subscribers > 500_000:
        score += 4
        reasons.append(
            "Large reach, but likely harder for an early-stage founder to access"
        )
    elif 100 <= subscribers < 1_000:
        score += 6
        reasons.append(
            "Small creator with potentially high outreach accessibility"
        )

    if videos >= 20:
        score += 5
        reasons.append("Established content history")

    # If we could not find any topic signal, keep the score low enough
    # that the creator will normally be filtered out.
    if not keyword_matches:
        score = min(score, 57)

    score = min(score, 98)

    if not reasons:
        reasons.append(
            f"Search result related to {audience}, but topic fit needs manual review"
        )

    return score, reasons


@app.post("/api/apps/{app_id}/discover/youtube")
def discover_youtube_creators(app_id: int):
    db = SessionLocal()

    try:
        app_record = (
            db.query(AppModel)
            .filter(AppModel.id == app_id)
            .first()
        )

        if not app_record:
            raise HTTPException(
                status_code=404,
                detail="App not found",
            )

        if not YOUTUBE_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="YouTube API key is not configured",
            )

        search_queries = [
            f"{app_record.audience} study tips",
            "university study tips",
            "study productivity",
            "exam preparation students",
            "student productivity",
        ]

        discovered_channels = {}

        for search_query in search_queries:
            response = httpx.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": search_query,
                    "type": "channel",
                    "maxResults": 5,
                    "key": YOUTUBE_API_KEY,
                },
                timeout=20.0,
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"YouTube API error: {response.text}",
                )

            data = response.json()

            for item in data.get("items", []):
                channel_id = item.get("id", {}).get("channelId")

                if not channel_id:
                    continue

                if channel_id in discovered_channels:
                    discovered_channels[channel_id]["matches"] += 1
                    discovered_channels[channel_id]["matched_queries"].append(
                        search_query
                    )
                    continue

                snippet = item.get("snippet", {})

                discovered_channels[channel_id] = {
                    "channel_id": channel_id,
                    "name": snippet.get("title", "Unknown creator"),
                    "description": snippet.get("description", ""),
                    "url": (
                        f"https://www.youtube.com/channel/{channel_id}"
                    ),
                    "matches": 1,
                    "matched_queries": [search_query],
                }

        channel_ids = list(discovered_channels.keys())
        channel_details = {}

        for i in range(0, len(channel_ids), 50):
            batch = channel_ids[i:i + 50]
            details = get_youtube_channel_details(batch)
            channel_details.update(details)

        ranked_channels = sorted(
            discovered_channels.values(),
            key=lambda creator: creator["matches"],
            reverse=True,
        )

        qualified_creators = []

        for creator in ranked_channels:
            details = channel_details.get(
                creator["channel_id"],
                {},
            )

            score, reasons = score_creator(
                creator,
                details,
                app_record.audience,
            )

            videos = details.get("video_count", 0)
            subscribers = details.get("subscriber_count", 0)

            # Reject inactive or extremely small channels
            if videos < 5:
                continue

            if subscribers < 50:
                continue

            # Reject weak matches
            if score < 58:
                continue

            creator["score"] = score
            creator["reasons"] = reasons
            creator["subscriber_count"] = details.get(
                "subscriber_count",
                0,
            )
            creator["video_count"] = details.get(
                "video_count",
                0,
            )
            creator["view_count"] = details.get(
                "view_count",
                0,
            )

            qualified_creators.append(creator)

        qualified_creators.sort(
            key=lambda creator: creator["score"],
            reverse=True,
        )

        creators = []

        for creator in qualified_creators[:10]:
            score = creator["score"]
            why_match = ". ".join(creator["reasons"])

            recommended_action = (
                f"Review the creator's recent content first. "
                f"If they regularly reach {app_record.audience}, "
                f"offer free access to {app_record.name} and ask "
                f"whether they would like to test it."
            )

            existing = (
                db.query(OpportunityModel)
                .filter(
                    OpportunityModel.app_id == app_record.id,
                    OpportunityModel.platform == "YouTube",
                    OpportunityModel.url == creator["url"],
                )
                .first()
            )

            if existing:
                existing.name = creator["name"]
                existing.description = creator["description"]
                existing.relevance_score = score
                existing.why_match = why_match
                existing.recommended_action = recommended_action
                existing.audience = app_record.audience
                existing.status = "new"

                creators.append(
                    {
                        "id": existing.id,
                        "name": existing.name,
                        "platform": existing.platform,
                        "url": existing.url,
                        "description": existing.description,
                        "relevance_score": existing.relevance_score,
                        "subscriber_count": creator["subscriber_count"],
                        "video_count": creator["video_count"],
                        "view_count": creator["view_count"],
                        "why_match": existing.why_match,
                        "recommended_action": existing.recommended_action,
                        "matched_queries": creator["matched_queries"],
                    }
                )
                continue

            opportunity = OpportunityModel(
                app_id=app_record.id,
                opportunity_type="creator",
                platform="YouTube",
                name=creator["name"],
                url=creator["url"],
                audience=app_record.audience,
                description=creator["description"],
                relevance_score=score,
                why_match=why_match,
                recommended_action=recommended_action,
                status="new",
            )

            db.add(opportunity)
            db.flush()

            creators.append(
                {
                    "id": opportunity.id,
                    "name": opportunity.name,
                    "platform": opportunity.platform,
                    "url": opportunity.url,
                    "description": opportunity.description,
                    "relevance_score": opportunity.relevance_score,
                    "subscriber_count": creator["subscriber_count"],
                    "video_count": creator["video_count"],
                    "view_count": creator["view_count"],
                    "why_match": opportunity.why_match,
                    "recommended_action": opportunity.recommended_action,
                    "matched_queries": creator["matched_queries"],
                }
            )

        db.commit()

        return {
            "app_id": app_record.id,
            "app_name": app_record.name,
            "audience": app_record.audience,
            "search_queries": search_queries,
            "unique_channels_found": len(discovered_channels),
            "qualified_channels": len(qualified_creators),
            "creators_returned": len(creators),
            "creators": creators,
        }

    finally:
        db.close()


def discover_reddit_communities_for_app(app_record):
    search_queries = [
        f"{app_record.audience} study",
        "university students",
        "study tips",
        "exam preparation",
        "student productivity",
    ]

    communities = {}

    headers = {
        "User-Agent": "LaunchPilotHackathon/1.0"
    }

    for query in search_queries:
        response = httpx.get(
            "https://www.reddit.com/subreddits/search.json",
            params={
                "q": query,
                "limit": 10,
            },
            headers=headers,
            timeout=20.0,
        )

        if response.status_code != 200:
            continue

        data = response.json()

        for item in data.get("data", {}).get("children", []):
            subreddit = item.get("data", {})

            name = subreddit.get("display_name")
            if not name:
                continue

            key = name.lower()

            if key in communities:
                communities[key]["matches"] += 1
                communities[key]["matched_queries"].append(query)
                continue

            communities[key] = {
                "name": name,
                "title": subreddit.get("title", ""),
                "description": subreddit.get("public_description", ""),
                "subscribers": subreddit.get("subscribers", 0),
                "url": f"https://www.reddit.com/r/{name}/",
                "matches": 1,
                "matched_queries": [query],
            }

    return list(communities.values())

@app.post("/api/apps/{app_id}/discover/reddit")
def discover_reddit_communities(app_id: int):
    db = SessionLocal()

    try:
        app_record = (
            db.query(AppModel)
            .filter(AppModel.id == app_id)
            .first()
        )

        if not app_record:
            raise HTTPException(
                status_code=404,
                detail="App not found",
            )

        results = discover_reddit_communities_for_app(app_record)

        ranked = []

        for community in results:
            text = (
                f"{community['name']} "
                f"{community['title']} "
                f"{community['description']}"
            ).lower()

            score = 45
            reasons = []

            keywords = [
                "student",
                "university",
                "college",
                "study",
                "exam",
                "productivity",
                "learning",
                "education",
            ]

            matches = [
                keyword
                for keyword in keywords
                if keyword in text
            ]

            score += min(len(matches) * 6, 30)

            if matches:
                reasons.append(
                    "Relevant topics: "
                    + ", ".join(matches[:4])
                )

            if community["matches"] > 1:
                score += min(
                    community["matches"] * 4,
                    12,
                )

                reasons.append(
                    f"Appeared in {community['matches']} relevant searches"
                )

            subscribers = community["subscribers"]

            if 1_000 <= subscribers <= 500_000:
                score += 10
                reasons.append(
                    "Active niche community size"
                )
            elif subscribers > 500_000:
                score += 5
                reasons.append(
                    "Large community with broad reach"
                )

            score = min(score, 98)

            if score < 58:
                continue

            ranked.append(
                {
                    **community,
                    "score": score,
                    "reasons": reasons,
                }
            )

        ranked.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        communities = []

        for community in ranked[:10]:
            existing = (
                db.query(OpportunityModel)
                .filter(
                    OpportunityModel.app_id == app_record.id,
                    OpportunityModel.platform == "Reddit",
                    OpportunityModel.url == community["url"],
                )
                .first()
            )

            why_match = ". ".join(
                community["reasons"]
            )

            recommended_action = (
                f"Open the subreddit and read its promotion rules first. "
                f"If product sharing is allowed, post a value-first message "
                f"focused on the problem {app_record.name} solves."
            )

            if existing:
                existing.relevance_score = community["score"]
                existing.why_match = why_match
                existing.recommended_action = recommended_action

                opportunity = existing

            else:
                opportunity = OpportunityModel(
                    app_id=app_record.id,
                    opportunity_type="community",
                    platform="Reddit",
                    name=f"r/{community['name']}",
                    url=community["url"],
                    audience=app_record.audience,
                    description=community["description"],
                    relevance_score=community["score"],
                    why_match=why_match,
                    recommended_action=recommended_action,
                    status="new",
                )

                db.add(opportunity)
                db.flush()

            communities.append(
                {
                    "id": opportunity.id,
                    "name": opportunity.name,
                    "platform": opportunity.platform,
                    "url": opportunity.url,
                    "description": opportunity.description,
                    "subscriber_count": community["subscribers"],
                    "relevance_score": opportunity.relevance_score,
                    "why_match": opportunity.why_match,
                    "recommended_action": opportunity.recommended_action,
                    "matched_queries": community["matched_queries"],
                }
            )

        db.commit()

        return {
            "app_id": app_record.id,
            "app_name": app_record.name,
            "communities_found": len(results),
            "communities_returned": len(communities),
            "communities": communities,
        }

    finally:
        db.close()

@app.post("/api/opportunities/{opportunity_id}/outreach")
def generate_outreach(opportunity_id: int):
    db = SessionLocal()

    try:
        opportunity = (
            db.query(OpportunityModel)
            .filter(OpportunityModel.id == opportunity_id)
            .first()
        )

        if not opportunity:
            raise HTTPException(
                status_code=404,
                detail="Opportunity not found",
            )

        app_record = (
            db.query(AppModel)
            .filter(AppModel.id == opportunity.app_id)
            .first()
        )

        if not app_record:
            raise HTTPException(
                status_code=404,
                detail="App not found",
            )

        if opportunity.opportunity_type == "creator":
            message = (
                f"Hi {opportunity.name},\n\n"
                f"I built {app_record.name}, a tool for "
                f"{app_record.audience}. "
                f"{app_record.description}\n\n"
                f"I thought it might fit your audience, so I'd love "
                f"to give you free access and let you try it in your "
                f"own workflow. No pressure to promote it — I'd "
                f"genuinely value your feedback first.\n\n"
                f"If you like it, we can also explore sharing it "
                f"with your audience."
            )

        elif opportunity.opportunity_type == "community":
            message = (
                f"Hi everyone — I'm building {app_record.name} for "
                f"{app_record.audience}.\n\n"
                f"{app_record.description}\n\n"
                f"I'm looking for a few early users to try it and "
                f"tell me what works and what doesn't. If this is "
                f"allowed here, I'd be happy to share access."
            )

        elif opportunity.opportunity_type == "partner":
            message = (
                f"Hi {opportunity.name},\n\n"
                f"I'm working on {app_record.name}, which serves "
                f"{app_record.audience}. {app_record.description}\n\n"
                f"It looks like we serve overlapping users without "
                f"directly competing, so I wondered if a small "
                f"cross-promotion or partnership could make sense."
            )

        else:
            message = (
                f"I'm testing {app_record.name} with a small group of "
                f"{app_record.audience}.\n\n"
                f"{app_record.description}\n\n"
                f"Would you be interested in trying it and giving "
                f"quick feedback?"
            )

        return {
            "opportunity_id": opportunity.id,
            "app_name": app_record.name,
            "type": opportunity.opportunity_type,
            "platform": opportunity.platform,
            "target": opportunity.name,
            "message": message,
        }

    finally:
        db.close()


@app.post("/api/apps/{app_id}/opportunities")
def create_opportunities(app_id: int):
    db = SessionLocal()

    try:
        app_record = (
            db.query(AppModel)
            .filter(AppModel.id == app_id)
            .first()
        )

        if not app_record:
            raise HTTPException(
                status_code=404,
                detail="App not found",
            )

        existing = (
            db.query(OpportunityModel)
            .filter(OpportunityModel.app_id == app_id)
            .all()
        )

        if existing:
            return {
                "app_id": app_record.id,
                "app_name": app_record.name,
                "opportunities": [
                    {
                        "id": item.id,
                        "type": item.opportunity_type,
                        "platform": item.platform,
                        "name": item.name,
                        "url": item.url,
                        "audience": item.audience,
                        "description": item.description,
                        "relevance_score": item.relevance_score,
                        "why_match": item.why_match,
                        "recommended_action": item.recommended_action,
                        "status": item.status,
                    }
                    for item in existing
                ],
            }

        opportunity_data = [
            {
                "type": "user",
                "platform": "Direct",
                "name": "Early user segment",
                "audience": app_record.audience,
                "description": (
                    f"People matching the main audience for "
                    f"{app_record.name}."
                ),
                "score": 95,
                "why": (
                    f"They directly match the target audience: "
                    f"{app_record.audience}."
                ),
                "action": (
                    "Use public conversations and opted-in channels "
                    "to find early users who are actively discussing "
                    "the problem."
                ),
            },
            {
                "type": "creator",
                "platform": "YouTube",
                "name": "Creator discovery",
                "audience": app_record.audience,
                "description": (
                    "Run the YouTube discovery mission to find "
                    "specific relevant creators."
                ),
                "score": 90,
                "why": (
                    "Creators can reach many potential users with "
                    "one collaboration."
                ),
                "action": (
                    "Run YouTube discovery, qualify the channels, "
                    "then contact only strong matches."
                ),
            },
            {
                "type": "community",
                "platform": "Reddit",
                "name": "Community discovery",
                "audience": app_record.audience,
                "description": (
                    "Find communities where target users already "
                    "discuss related problems."
                ),
                "score": 88,
                "why": (
                    "The audience already gathers there around "
                    "shared problems and interests."
                ),
                "action": (
                    "Read community rules and use value-first "
                    "promotion instead of spam."
                ),
            },
            {
                "type": "partner",
                "platform": "Web",
                "name": "Partner discovery",
                "audience": app_record.audience,
                "description": (
                    "Find complementary founders, products, "
                    "newsletters and organizations serving the same audience."
                ),
                "score": 82,
                "why": (
                    "Shared audiences create opportunities for "
                    "cross-promotion and partnerships."
                ),
                "action": (
                    "Approach complementary partners with a specific "
                    "cross-promotion idea."
                ),
            },
        ]

        created = []

        for item in opportunity_data:
            opportunity = OpportunityModel(
                app_id=app_record.id,
                opportunity_type=item["type"],
                platform=item["platform"],
                name=item["name"],
                audience=item["audience"],
                description=item["description"],
                relevance_score=item["score"],
                why_match=item["why"],
                recommended_action=item["action"],
            )

            db.add(opportunity)
            db.flush()

            created.append(
                {
                    "id": opportunity.id,
                    "type": opportunity.opportunity_type,
                    "platform": opportunity.platform,
                    "name": opportunity.name,
                    "audience": opportunity.audience,
                    "description": opportunity.description,
                    "relevance_score": opportunity.relevance_score,
                    "why_match": opportunity.why_match,
                    "recommended_action": opportunity.recommended_action,
                    "status": opportunity.status,
                }
            )

        db.commit()

        return {
            "app_id": app_record.id,
            "app_name": app_record.name,
            "opportunities": created,
        }

    finally:
        db.close()


@app.post("/api/apps/{app_id}/generate")
def generate_campaigns(app_id: int):
    db = SessionLocal()

    try:
        app_record = (
            db.query(AppModel)
            .filter(AppModel.id == app_id)
            .first()
        )

        if not app_record:
            raise HTTPException(
                status_code=404,
                detail="App not found",
            )

        campaign_data = [
            {
                "channel": "TikTok",
                "title": "Pain Point Hook",
                "content": (
                    f"POV: you're part of {app_record.audience} "
                    f"and you're tired of the same problem. "
                    f"{app_record.name} helps by "
                    f"{app_record.description} "
                    f"Try it here:"
                ),
            },
            {
                "channel": "X",
                "title": f"Introducing {app_record.name}",
                "content": (
                    f"We built {app_record.name} "
                    f"for {app_record.audience}.\n\n"
                    f"{app_record.description}\n\n"
                    f"Our goal: {app_record.goal}\n\n"
                    f"Try it:"
                ),
            },
            {
                "channel": "WhatsApp",
                "title": "Share With Friends",
                "content": (
    f"Found something useful: {app_record.name}.\n\n"
    f"{app_record.description}\n\n"
    f"If you're a {app_record.audience.rstrip('s')}, "
    f"or know someone who could use this, check it out:"
),
            },
        ]

        created_campaigns = []

        for item in campaign_data:
            campaign = CampaignModel(
                app_id=app_record.id,
                channel=item["channel"],
                title=item["title"],
                content=item["content"],
                tracking_code=str(uuid.uuid4())[:8],
            )

            db.add(campaign)
            db.commit()
            db.refresh(campaign)

            created_campaigns.append(
                {
                    "id": campaign.id,
                    "channel": campaign.channel,
                    "title": campaign.title,
                    "content": campaign.content,
                    "tracking_code": campaign.tracking_code,
                }
            )

        return {
            "app_id": app_record.id,
            "app_name": app_record.name,
            "campaigns": created_campaigns,
        }

    finally:
        db.close()
