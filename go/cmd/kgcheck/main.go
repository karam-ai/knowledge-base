package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"net/http"
	"os"
	"time"
)

type queryRequest struct {
	Query string `json:"query"`
}

type queryResponse struct {
	Boolean *bool             `json:"boolean,omitempty"`
	Rows    []map[string]any  `json:"rows,omitempty"`
}

func check(endpoint, query string) error {
	body, err := json.Marshal(queryRequest{Query: query})
	if err != nil {
		return err
	}
	client := &http.Client{Timeout: 10 * time.Second}
	response, err := client.Post(endpoint+"/v1/sparql", "application/json", bytes.NewReader(body))
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("SPARQL endpoint returned %s", response.Status)
	}
	var result queryResponse
	if err := json.NewDecoder(response.Body).Decode(&result); err != nil {
		return err
	}
	if result.Boolean != nil && !*result.Boolean {
		return fmt.Errorf("ASK query returned false")
	}
	return nil
}

func main() {
	endpoint := flag.String("endpoint", "http://127.0.0.1:8000", "podcast-kg API base URL")
	query := flag.String("query", "ASK { ?s ?p ?o }", "read-only SPARQL ASK or SELECT query")
	flag.Parse()
	if err := check(*endpoint, *query); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println("podcast knowledge graph is healthy")
}
