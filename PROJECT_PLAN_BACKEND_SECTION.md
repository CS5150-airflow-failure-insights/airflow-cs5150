# Airflow Failure Insights - Backend & Integration Architecture

## 1. BACKEND TECHNOLOGY STACK

### 1.1 Language & Runtime Requirements
- **Python Version**: 3.10+ (following current Airflow 3.x requirements)
  - Airflow core uses Python 3.10, 3.11, 3.12, 3.13
  - All code must be compatible with these versions
  - Type hints using `from __future__ import annotations` for forward compatibility

### 1.2 ORM & Database Layer
- **ORM Framework**: SQLAlchemy 2.0+
  - Airflow uses SQLAlchemy as the canonical ORM
  - All database models must inherit from `Base` class in `airflow.models.base`
  - All models use declarative (Mapped) column definitions with proper type hints
  
- **Migration Tool**: Alembic
  - Database schema changes managed through Alembic migrations
  - Located in: `airflow-core/src/airflow/migrations/versions/`
  - All new tables require corresponding migration files
  - Pattern: `alembic/versions/XXXX_date_description.py`

### 1.3 Key Dependencies Already in Airflow
- **SQLAlchemy Core**: Query building, type system
- **SQLAlchemy ORM**: `relationship`, `ForeignKey`, `Index`, decorators
- **Alembic**: Schema versioning and migrations
- **Pydantic**: Request/response validation in FastAPI (v2+)
- **FastAPI**: REST API framework with OpenAPI support
- **Structlog**: Structured logging (used throughout Airflow)

---

## 2. DATABASE ARCHITECTURE

### 2.1 Supported Database Systems

| Database | Support Level | Production-Ready | Notes |
|----------|---------------|--------------------|-------|
| PostgreSQL 14+ | **Primary** | Yes | Recommended for production; supports JSONB, UUID, advanced indexing |
| MySQL 8.0+ | Supported | Yes | Compatible but less feature-rich than PostgreSQL |
| SQLite 3.15+ | Development Only | **No** | Used for testing; NOT recommended for production |

**Determination**: Check Airflow's runtime configuration in `airflow.cfg` or environment variable `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` to identify the backend being used.

### 2.2 Database Connection Architecture

```
┌─────────────────────────────────────────────────┐
│ Airflow Failure Insights Features               │
├─────────────────────────────────────────────────┤
│ ↓                                               │
│ SQLAlchemy ORM Layer (Models)                   │
│ ├─ ErrorPattern                                 │
│ ├─ ErrorNote                                    │
│ ├─ ErrorTaskInstanceMap                        │
│ └─ [Relationships to existing models]          │
├─────────────────────────────────────────────────┤
│ ↓                                               │
│ SQLAlchemy Session Management                   │
│ ├─ SessionDep (FastAPI dependency)             │
│ ├─ provide_session decorator                    │
│ └─ Transaction handling                        │
├─────────────────────────────────────────────────┤
│ ↓                                               │
│ Database Connection Pool (Configured in Airflow)│
│ ├─ PostgreSQL: psycopg2/asyncpg               │
│ ├─ MySQL: PyMySQL/pymysql                     │
│ └─ SQLite: sqlite3                            │
├─────────────────────────────────────────────────┤
│ ↓                                               │
│ Physical Database Backend                      │
└─────────────────────────────────────────────────┘
```

### 2.3 New Database Tables

#### Table 1: `error_pattern`
**Purpose**: Store normalized error signatures and their metadata

```sql
CREATE TABLE error_pattern (
    id VARCHAR(36) PRIMARY KEY,  -- UUID as string
    error_signature VARCHAR(64) NOT NULL,  -- SHA256 hash of normalized error
    error_template TEXT NOT NULL,  -- Regex/template representation
    first_occurrence_at TIMESTAMP NOT NULL,  -- When first seen
    last_occurrence_at TIMESTAMP NOT NULL,  -- Last seen
    occurrence_count INTEGER DEFAULT 1,  -- How many times detected
    is_active BOOLEAN DEFAULT TRUE,  -- Soft delete support
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    
    -- Indexes for query performance
    UNIQUE INDEX idx_error_signature (error_signature),
    INDEX idx_last_occurrence_at (last_occurrence_at),
    INDEX idx_is_active (is_active),
    INDEX idx_occurrence_count (occurrence_count DESC)
);
```

**Access Pattern**:
- Fast lookup: Query by `error_signature` (hash)
- Recent errors: Query by `last_occurrence_at DESC LIMIT 10`
- Frequency ranking: Query by `occurrence_count DESC`

#### Table 2: `error_note`
**Purpose**: Store user annotations and knowledge for error patterns

```sql
CREATE TABLE error_note (
    id VARCHAR(36) PRIMARY KEY,  -- UUID as string
    error_pattern_id VARCHAR(36) NOT NULL,  -- FK to error_pattern
    content TEXT NOT NULL,  -- Markdown-formatted annotation
    author VARCHAR(256) NOT NULL,  -- Username who created
    tags JSON,  -- {"tags": ["database", "timeout", "s3"]}
    documentation_links JSON,  -- {"links": ["https://wiki.../fix", ...]}
    is_verified BOOLEAN DEFAULT FALSE,  -- Flag for review/moderation
    verification_notes TEXT,  -- Admin comments
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    
    -- Foreign key constraint
    CONSTRAINT fk_error_note_pattern 
        FOREIGN KEY (error_pattern_id) 
        REFERENCES error_pattern(id) 
        ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_error_pattern_id (error_pattern_id),
    INDEX idx_author (author),
    INDEX idx_is_verified (is_verified),
    INDEX idx_created_at (created_at DESC)
);
```

**Access Pattern**:
- Get notes for error: Query by `error_pattern_id`
- User's contributions: Query by `author`
- Pending review: Query by `is_verified = FALSE`

#### Table 3: `error_task_instance_map`
**Purpose**: Link errors to specific task instance executions (many-to-many)

```sql
CREATE TABLE error_task_instance_map (
    id VARCHAR(36) PRIMARY KEY,  -- UUID as string
    error_pattern_id VARCHAR(36) NOT NULL,  -- FK to error_pattern
    task_instance_id VARCHAR(36) NOT NULL,  -- FK to task_instance.id
    dag_id VARCHAR(250) NOT NULL,  -- Denormalized for query performance
    task_id VARCHAR(250) NOT NULL,  -- Denormalized for query performance
    run_id VARCHAR(250) NOT NULL,  -- Denormalized for query performance
    map_index INTEGER DEFAULT -1,  -- Denormalized for query performance
    error_location_in_log INTEGER,  -- Line number or byte offset where error appears
    log_try_number INTEGER,  -- Which attempt (try_number from task_instance)
    created_at TIMESTAMP NOT NULL,
    
    -- Foreign key constraints
    CONSTRAINT fk_etim_pattern 
        FOREIGN KEY (error_pattern_id) 
        REFERENCES error_pattern(id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_etim_task_instance 
        FOREIGN KEY (task_instance_id) 
        REFERENCES task_instance(id) 
        ON DELETE CASCADE,
    
    -- Composite indexes for query patterns
    INDEX idx_pattern_id (error_pattern_id),
    INDEX idx_task_instance_id (task_instance_id),
    INDEX idx_dag_run (dag_id, run_id),
    UNIQUE INDEX idx_composite 
        (error_pattern_id, task_instance_id, error_location_in_log)
);
```

**Access Pattern**:
- Find all instances of error: Query by `error_pattern_id`
- Find errors for task: Query by `dag_id, task_id, run_id`
- Find errors across DAGs: Query by `error_pattern_id, dag_id`

#### Table 4: `error_note_audit_log` (Optional)
**Purpose**: Maintain audit trail for compliance/debugging

```sql
CREATE TABLE error_note_audit_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    error_note_id VARCHAR(36) NOT NULL,
    action VARCHAR(50),  -- 'CREATE', 'UPDATE', 'DELETE'
    actor VARCHAR(256),  -- Username performing action
    changes JSON,  -- {"before": {...}, "after": {...}}
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_error_note_id (error_note_id),
    INDEX idx_timestamp (timestamp DESC)
);
```

### 2.4 Relationships Diagram

```
┌─────────────────────────┐
│   error_pattern         │
├─────────────────────────┤
│ id (PK)                 │
│ error_signature (UNIQUE)│
│ error_template          │
│ occurrence_count        │
│ first_occurrence_at     │
│ last_occurrence_at      │
└────────────┬────────────┘
             │ (1:many)
             │
    ┌────────┴────────┬──────────────┐
    │                 │              │
    ↓                 ↓              ↓
┌──────────────┐  ┌────────────────────────┐
│ error_note   │  │ error_task_instance_map│
├──────────────┤  ├────────────────────────┤
│ id (PK)      │  │ id (PK)                │
│ content      │  │ error_pattern_id (FK)  │
│ author       │  │ task_instance_id (FK)  │
│ tags         │  │ dag_id (denorm)        │
│ is_verified  │  │ task_id (denorm)       │
└──────────────┘  │ run_id (denorm)        │
                  │ map_index (denorm)     │
                  │ error_location_in_log  │
                  └────────┬────────────────┘
                           │ (many:1)
                           │
                           ↓
                  ┌──────────────────────┐
                  │   task_instance      │
                  │   (Existing Airflow) │
                  └──────────────────────┘
```

---

## 3. LOG SYSTEM INTEGRATION

### 3.1 Airflow's Log Architecture (Current State)

Airflow separates logs into two categories:

#### Category A: Task Execution Logs
- **Storage**: Remote backends (S3, GCS, Azure Blob, local filesystem)
- **Access**: Via `TaskLogReader` class
- **Handler**: Configured in `file_task_handler.py`
- **NOT in database** - too large, accessed on-demand
- **Location**: `airflow-core/src/airflow/utils/log/file_task_handler.py`

#### Category B: Event Logs
- **Storage**: Airflow database (table: `log`)
- **Model**: `airflow.models.log.Log`
- **Content**: Task state transitions, scheduler events
- **Fields**: `event`, `dag_id`, `task_id`, `run_id`, `extra`

### 3.2 Integration Points for Error Insights

#### Integration Point 1: Log Retrieval Enhancement
**File**: `airflow-core/src/airflow/api_fastapi/core_api/routes/public/log.py`
**Current Flow**:
```
API Request (/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}/logs/{try_number})
    ↓
TaskLogReader.get_logs()
    ↓
Remote Storage (S3, GCS, local FS)
    ↓
Return log content to client
```

**Enhanced Flow**:
```
API Request
    ↓
TaskLogReader.get_logs()
    ↓
Remote Storage
    ↓
[NEW] Error Pattern Matching Service
    ↓
[NEW] Enrich log response with error annotations
    ↓
Return enhanced log + annotations to client
```

#### Integration Point 2: Log Storage & Handler
**File**: `airflow-core/src/airflow/utils/log/file_task_handler.py`
**Current Behavior**:
- Writes logs to configured remote backend
- Handles rotation, cleanup
- No error signature extraction

**Enhancement Strategy**:
- Hook into `emit()` method (when log messages are written)
- Extract error patterns from logged messages in real-time
- Store error signatures to database for later querying
- Minimal performance impact (async processing)

#### Integration Point 3: Dependency Chain Access
**Files**: 
- `airflow-core/src/airflow/models/dag.py` - DAG structure
- `airflow-core/src/airflow/models/dagrun.py` - Run dependencies
- `airflow-core/src/airflow/models/taskinstance.py` - Task state & relationships

**Current DAG Structure**:
```python
dag = dag_model.get_dag()  # Loaded from database
task = dag.get_task(task_id)  # Get task by ID
upstream_tasks = task.upstream_list  # Get dependencies
downstream_tasks = task.downstream_list
```

**Enhancement**: For root cause discovery, traverse:
```
Failed Task 
    ↓ (upstream_list)
Upstream Task A (state = FAILED)
    ↓ (upstream_list)
Upstream Task B (state = FAILED)  ← ROOT CAUSE
    ↓ (upstream_list)
Task C (state = SUCCESS)
```

---

## 4. CODE INTEGRATION APPROACH: OVERLAY ARCHITECTURE

### 4.1 Overlay Design Philosophy

The system is designed as a **non-invasive overlay** on Airflow's existing log and dependency infrastructure:

```
┌──────────────────────────────────────────────────────────────┐
│           AIRFLOW FAILURE INSIGHTS OVERLAY                  │
│  (New Services, Models, API Routes)                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ EXISTING AIRFLOW CORE (Unchanged)                      │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ • Log retrieval (file_task_handler.py)               │ │
│  │ • Task execution (models/taskinstance.py)            │ │
│  │ • DAG structure (models/dag.py)                      │ │
│  │ • Dependencies (models/dagrun.py)                    │ │
│  │ • Database ORM (SQLAlchemy)                          │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Principle**: Hook into existing systems without modifying core Airflow logic

### 4.2 Integration Strategy by Component

#### Strategy A: Log Loading Integration

**Approach**: Intercept at API layer (not at file handler layer)

```python
# Location: airflow-core/src/airflow/api_fastapi/core_api/routes/public/log.py

@app.get("/logs/{task_id}/logs/{try_number}")
def get_log(dag_id, dag_run_id, task_id, try_number, ...):
    # 1. Call existing TaskLogReader
    log_content = task_log_reader.get_logs(dag_id, task_id, dag_run_id, try_number)
    
    # 2. [NEW] Analyze logs for error patterns
    error_patterns = error_analyzer.analyze_log(log_content)
    
    # 3. [NEW] Fetch error notes associated with patterns
    error_notes = fetch_error_notes_for_patterns(error_patterns)
    
    # 4. Return enhanced response
    return {
        "log_content": log_content,
        "error_annotations": error_notes,  # NEW field
        "error_patterns": error_patterns    # NEW field
    }
```

**Rationale**:
- Non-invasive: Existing log retrieval unchanged
- Backward compatible: Old clients still work (new fields optional)
- Lazy evaluation: Error analysis only happens when logs are requested
- Cacheable: Can cache results at API layer

#### Strategy B: Dependency Chain Integration

**Approach**: Query existing TaskInstance relationships

```python
# Location: airflow-core/src/airflow/services/error_analysis.py

class FailureAnalyzer:
    def find_root_cause(self, task_instance):
        # Use existing TaskInstance relationships
        current = task_instance
        failed_chain = [current]
        
        while current.upstream_list:
            # Get upstream tasks from current task
            upstream = current.upstream_list
            
            # Query database for their state
            upstream_tis = session.query(TaskInstance).filter(
                TaskInstance.task_id.in_([t.task_id for t in upstream]),
                TaskInstance.run_id == current.run_id,
                TaskInstance.state == TaskInstanceState.FAILED
            ).all()
            
            if not upstream_tis:
                break
            
            # Take first failed, continue traversal
            current = upstream_tis[0]
            failed_chain.append(current)
        
        return failed_chain[-1]  # Root cause
```

**Rationale**:
- Uses only existing Airflow APIs
- No modification to core scheduler logic
- Reads from existing database relationships
- Can be called independently anytime

#### Strategy C: Error Pattern Extraction

**Approach**: Process logs after retrieval, extract signatures

```python
# Location: airflow-core/src/airflow/services/error_matching.py

class ErrorSignatureGenerator:
    def extract_errors(self, log_content: str) -> list[str]:
        """Extract error lines from log."""
        error_patterns = [
            r"ERROR\s*-\s*.*",
            r"Exception:\s*.*",
            r"failed.*",
            r"traceback.*"
        ]
        
        errors = []
        for pattern in error_patterns:
            matches = re.findall(pattern, log_content, re.IGNORECASE)
            errors.extend(matches)
        
        return errors
    
    def normalize_error(self, error: str) -> str:
        """Remove variable parts (timestamps, IDs, etc)."""
        # Remove timestamps: "2024-01-15 10:30:45" → "[TIMESTAMP]"
        normalized = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', '[TIMESTAMP]', error)
        
        # Remove file paths: "/var/lib/airflow/..." → "[PATH]"
        normalized = re.sub(r'/[\w/.-]+', '[PATH]', normalized)
        
        # Remove session IDs: "session_12345" → "session_[ID]"
        normalized = re.sub(r'(session|id|token)_\w+', r'\1_[ID]', normalized)
        
        return normalized.lower()
    
    def generate_signature(self, normalized_error: str) -> str:
        """Create SHA256 hash."""
        return hashlib.sha256(normalized_error.encode()).hexdigest()
```

**Rationale**:
- Parallel processing independent of log storage
- Hooks into existing TaskLogReader output
- Stateless (can scale horizontally)
- Privacy-by-design (hash-based signatures)

### 4.3 Database Transaction Management

**Pattern**: Follow existing Airflow conventions

```python
# Use FastAPI dependency injection (existing pattern in Airflow)
from airflow.api_fastapi.common.db.common import SessionDep

@router.post("/error-notes")
def create_error_note(
    body: ErrorNoteRequest,
    session: SessionDep,  # SQLAlchemy session auto-managed
) -> ErrorNoteResponse:
    """
    Session is:
    - Created before handler
    - Committed after handler
    - Rolled back on exception
    - Auto-closed in finally block
    """
    error_pattern = session.query(ErrorPattern).filter(...).one()
    new_note = ErrorNote(content=body.content, error_pattern=error_pattern)
    
    session.add(new_note)
    session.flush()  # Get ID
    
    return ErrorNoteResponse.from_orm(new_note)
```

**Rationale**:
- Uses proven Airflow pattern
- Automatic transaction handling
- Consistency with existing code
- Proper session lifecycle management

### 4.4 Performance Considerations

#### Query Optimization
```python
# Use SQLAlchemy eager loading to avoid N+1 queries
query = session.query(ErrorPattern)\
    .options(
        joinedload(ErrorPattern.notes),  # Load related notes
        joinedload(ErrorPattern.task_instances)  # Load TI map
    )\
    .filter(ErrorPattern.error_signature == sig)
```

#### Indexing Strategy
All new tables have strategic indexes:
- Hash-based lookups: `error_signature` UNIQUE index
- Time-based queries: `last_occurrence_at` index
- Relationship traversal: Foreign key indexes
- DAG queries: Composite (`dag_id`, `run_id`) index

#### Caching Layer (Optional Future)
```
API Request
    ↓
Redis Cache Check (TTL: 5 minutes)
    ↓ (miss)
Error Pattern Lookup
    ↓
Cache Result
    ↓
Return to Client
```

### 4.5 Migration & Deployment Strategy

**Phase 1: Inactive State**
```python
# System deployed but feature flag disabled
if FEATURE_FLAG_ENABLED:
    # Error analysis happens
    error_analysis.analyze_logs()
else:
    # Everything bypassed, zero overhead
    pass
```

**Phase 2: Shadow Mode**
- Error patterns collected but not displayed
- Allows validation of algorithm accuracy
- Data collected for 1-2 weeks

**Phase 3: Active Rollout**
- Errors annotations visible in UI
- Full feature enabled
- Rollback capability via feature flag

---

## 5. EXISTING AIRFLOW FILE REFERENCES

### Key Files to Integrate With:

| File | Purpose | Integration Point |
|------|---------|-------------------|
| `models/taskinstance.py` | Task execution state | Read `state`, `upstream_list` |
| `models/dagrun.py` | DAG run state | Read `run_id`, `dag_id`, relationships |
| `models/dag.py` | DAG structure | Read task dependencies |
| `models/log.py` | Event log model | Reference pattern for new models |
| `utils/log/file_task_handler.py` | Log writing | Understand log format |
| `utils/log/log_reader.py` | Log reading | Hook into log retrieval |
| `api_fastapi/core_api/routes/public/log.py` | Log API | Enhance response |
| `api_fastapi/common/db/common.py` | Session management | Use SessionDep pattern |
| `configuration.py` | Config system | Optional: new config flags |
| `models/base.py` | ORM base | Inherit for new models |

---

## 6. TECHNOLOGY CHOICES & JUSTIFICATIONS

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Python | 3.10+ | Match Airflow requirements |
| ORM | SQLAlchemy 2.0+ | Airflow standard; type-safe |
| Database | PostgreSQL primary | Best performance + JSONB support |
| API | FastAPI | Type-safe; async ready |
| Validation | Pydantic v2 | FastAPI integration; defaults to strict mode |
| Hashing | SHA-256 | Cryptographic; built-in python hashlib |
| String Match | difflib + regex | stdlib; no external deps |
| Logging | structlog | Airflow standard; structured output |
| Testing | pytest + SQLAlchemy test helpers | Airflow convention |

---

## 7. DEPLOYMENT CHECKLIST

- [ ] Database schema created (migration files)
- [ ] Schema tested on all 3 DB backends (PostgreSQL, MySQL, SQLite)
- [ ] Connection pooling configured
- [ ] Error analysis service deployed with feature flag OFF
- [ ] Error pattern collection running in shadow mode
- [ ] Validation period complete (1-2 weeks)
- [ ] UI components merged
- [ ] Feature flag enabled for 10% of users (canary)
- [ ] Monitor error rates, query performance
- [ ] Roll out to 100% of users
- [ ] Set up maintenance jobs (cleanup old patterns, audit logging)
