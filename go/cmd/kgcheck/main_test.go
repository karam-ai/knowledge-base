package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestCheckAcceptsSuccessfulAsk(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/sparql" {
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]bool{"boolean": true})
	}))
	defer server.Close()

	if err := check(server.URL, "ASK { ?s ?p ?o }"); err != nil {
		t.Fatal(err)
	}
}

func TestCheckRejectsFalseAsk(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]bool{"boolean": false})
	}))
	defer server.Close()

	if err := check(server.URL, "ASK { ?s ?p ?o }"); err == nil {
		t.Fatal("expected false ASK query to fail")
	}
}
