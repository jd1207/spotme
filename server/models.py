from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from server.database import Base

class Program(Base):
    __tablename__ = "programs"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    goal = Column(String, nullable=False)
    phase = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Workout(Base):
    __tablename__ = "workouts"
    id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey("programs.id"))
    date = Column(String, nullable=False)
    type = Column(String, nullable=False)
    duration = Column(Integer, nullable=True)
    whoop_recovery = Column(Float, nullable=True)
    whoop_strain = Column(Float, nullable=True)
    status = Column(String, default="active")
    notes = Column(Text, nullable=True)

class Exercise(Base):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True)
    workout_id = Column(Integer, ForeignKey("workouts.id"))
    name = Column(String, nullable=False)
    order = Column(Integer, nullable=False)
    notes = Column(Text, nullable=True)

class Set(Base):
    __tablename__ = "sets"
    id = Column(Integer, primary_key=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"))
    weight = Column(Float, nullable=False)
    reps = Column(Integer, nullable=False)
    rpe = Column(Float, nullable=True)
    completed = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    target_weight = Column(Float, nullable=True)
    target_reps = Column(Integer, nullable=True)
    set_type = Column(String, nullable=True)
    order = Column(Integer, nullable=True)
    status = Column(String, nullable=True)

class WhoopData(Base):
    __tablename__ = "whoop_data"
    id = Column(Integer, primary_key=True)
    date = Column(String, nullable=False)
    recovery_score = Column(Float)
    hrv = Column(Float)
    resting_hr = Column(Integer)
    sleep_score = Column(Float)
    sleep_duration = Column(Float)
    strain = Column(Float)
    synced_at = Column(DateTime, server_default=func.now())

class FormCheck(Base):
    __tablename__ = "form_checks"
    id = Column(Integer, primary_key=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=True)
    set_id = Column(Integer, ForeignKey("sets.id"), nullable=True)
    video_path = Column(String)
    frames_extracted = Column(Integer, default=0)
    claude_analysis = Column(Text, nullable=True)
    flagged_issues = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True)
    workout_id = Column(Integer, ForeignKey("workouts.id"), nullable=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    context_type = Column(String, default="chat")
    date = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class UserProfile(Base):
    __tablename__ = "user_profiles"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, default="")
    goals = Column(String, nullable=True)
    experience_level = Column(String, nullable=True)
    equipment = Column(String, nullable=True)
    training_frequency = Column(String, nullable=True)
    injuries_notes = Column(Text, nullable=True)
    preferences = Column(Text, nullable=True)
    calorie_target = Column(Integer, nullable=True)
    protein_target = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SystemMemory(Base):
    __tablename__ = "system_memory"
    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False, unique=True)
    content = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WhoopToken(Base):
    __tablename__ = "whoop_tokens"
    id = Column(Integer, primary_key=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WhoopSyncQueue(Base):
    __tablename__ = "whoop_sync_queue"
    id = Column(Integer, primary_key=True)
    workout_id = Column(Integer, ForeignKey("workouts.id"))
    payload = Column(Text, nullable=False)
    status = Column(String, default="pending")
    retries = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Meal(Base):
    __tablename__ = "meals"
    id = Column(Integer, primary_key=True)
    date = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    calories = Column(Integer, nullable=True)
    protein = Column(Float, nullable=True)
    carbs = Column(Float, nullable=True)
    fat = Column(Float, nullable=True)
    meal_type = Column(String, nullable=True)
    items = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
