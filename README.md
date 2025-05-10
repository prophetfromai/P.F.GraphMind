# Neo4j FastAPI Application

A simple FastAPI application that connects to a local Neo4j database. 
Converts journal entries into embeddings, searches for the most similar entries
that already exist in the database, starting with the closest match uses the elo 
ranking system to compare your current idea against the existing ideas and decides to 
either add a new entry, extend an existing entry or update an equal entry with your
newest description, updates the knowledge graph. 



## Prerequisites

- Python 3.8 or higher
- Neo4j Desktop installed and running locally
- Neo4j database running on default port (7687)

## Setup

1. **Install Neo4j Desktop**:
   - Download and install Neo4j Desktop from [neo4j.com/download](https://neo4j.com/download/)
   - Create a new database
   - Set the password to "password" (or update the .env file with your chosen password)
   - Start the database

2. **Create index and vector space for embedding**:
   CREATE VECTOR INDEX conceptVectorIndex IF NOT EXISTS
   FOR (c:Concept)
   ON (c.embedding)
   OPTIONS { indexConfig: {
   `vector.dimensions`: 1536,
   `vector.similarity_function`: 'cosine'
   }}

3. **Install Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**:
   The application uses the following environment variables (already set in .env):
   ```
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=password
   NEO4J_DATABASE=neo4j
   ```
   If you used a different password during Neo4j setup, update the `NEO4J_PASSWORD` in the `.env` file.
   NOTE don't bother changing the db name, leave it as the default, it database is not a production supported feature of local hosting the db. 

## Running the Application

1. Start the FastAPI server:
   ```bash
   uvicorn app.main:app --reload
   ```

2. The application will be available at:
   - API: http://localhost:8000/api/v1
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/api/v1/health
   - OpenAPI Schema: http://localhost:8000/openapi.json

## Testing the Connection

1. Visit http://localhost:8000/health in your browser or use curl:
   ```bash
   curl http://localhost:8000/health
   ```

2. You should see a response like:
   ```json
   {
     "status": "healthy",
     "database": "connected"
   }
   ```

## Troubleshooting

Always append any serious issues to this list with information on how to avoid them.

If you encounter connection issues:
1. Verify Neo4j Desktop is running
2. Check if the database is started
3. Verify the credentials in `.env` match your Neo4j setup