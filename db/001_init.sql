CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE sources (id text PRIMARY KEY, title text NOT NULL, url text NOT NULL, license_evidence text, approval_status text NOT NULL CHECK (approval_status IN ('pending','approved','rejected')));
CREATE TABLE stations (id text PRIMARY KEY, source_id text REFERENCES sources(id), location geometry(Point,4326) NOT NULL, vertical_datum text NOT NULL);
CREATE INDEX stations_location_idx ON stations USING gist(location);
CREATE TABLE observations (station_id text REFERENCES stations(id), observed_at timestamptz NOT NULL, ingested_at timestamptz NOT NULL DEFAULT now(), value double precision NOT NULL CHECK(value > '-Infinity'::float8 AND value < 'Infinity'::float8), unit text NOT NULL, raw_sha256 text NOT NULL, PRIMARY KEY(station_id, observed_at));
CREATE TABLE river_reaches (id text PRIMARY KEY, downstream_id text REFERENCES river_reaches(id) DEFERRABLE INITIALLY DEFERRED, geom geometry(LineString,4326) NOT NULL, source_id text REFERENCES sources(id));
CREATE TABLE model_runs (id uuid PRIMARY KEY, model_version text NOT NULL, generated_at timestamptz NOT NULL, valid_from timestamptz NOT NULL, valid_to timestamptz NOT NULL, coverage geometry(MultiPolygon,4326), vertical_datum text NOT NULL, input_manifest jsonb NOT NULL, validation_report jsonb NOT NULL, approval_status text NOT NULL DEFAULT 'pending', CHECK (valid_to > valid_from));
CREATE TABLE ingest_log (id bigserial PRIMARY KEY, source_id text REFERENCES sources(id), started_at timestamptz DEFAULT now(), status text NOT NULL, raw_sha256 text, detail text);
