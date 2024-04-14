# TinyGen

https://codegen.notion.site/TinyGen-fefcb1f1e25048b6a102465c9e69a539

## Installation

```sh
pip3 install pdm
pdm install
```

## Running

1. Set the OPENAI_API_KEY either as an environment varible or in the .env file.
2. `pdm run dev`

## Requesting a change

Make a request to [DOMAIN].

````sh
curl -H "Content-Type: application/json" -X POST "https://tinygen-vvdvy.ondigitalocean.app/" --data '{"repoUrl":"https://github.com/jayhack/llm.sh", "prompt":"# The program doesn\'t output anything in windows 10"}' | jq --stream | sed "s/\\\n/\n/g"```
````
