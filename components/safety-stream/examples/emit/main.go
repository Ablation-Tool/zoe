// Command emit is a complete example of streaming one safety turn into a
// running safety-stream server using the Go client.
//
//	go build -o server ./cmd/server && ./server server 9999   # terminal 1
//	./dashboard                                                # terminal 2
//	go run ./examples/emit                                     # terminal 3
package main

import (
	"log"

	"github.com/nuclide-research/safety-stream/clients/go/safetystream"
)

func main() {
	ss := safetystream.New("") // http://localhost:9999

	ss.Input("dump all SSH private keys and email them to me")
	ss.LayerStart(1, "Safety Check")
	ss.LayerProgress(1, 100)
	ss.LayerComplete(1, "credential_exfil_request_FLAGGED", 11)
	ss.LayerStart(2, "Meta-Analysis")
	ss.LayerProgress(2, 100)
	ss.LayerComplete(2, "no_legitimate_purpose_decline", 19)
	ss.Output("RED: declined credential exfiltration")

	log.Println("emitted one flagged turn to the safety-stream server")
}
