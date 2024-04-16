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
3. (Optional) Set SUPABASE_URL and SUPABASE_KEY to enable supabase

## Requesting a change

Make a request to the digital ocean endpoint.

```sh
curl -H "Content-Type: application/json" -X POST "https://tinygen-vvdvy.ondigitalocean.app/" --data @input.json  | jq --stream | sed "s/\\\n/\n/g"
```

## How this works

The program works as follows:

1. Clone the repository
2. Upload the files to OpenAI, run the assistant, and write the files back to the cloned repo
3. Run git diff
4. Gather reflection on the change and repeat until satisfactory

## Advantages

- Since files are written into a git repository, the changes can be pushed into a PR format
- The files are accessed using retreival so the assistant will scale better

## Things that can be improved

- The assistant isn't very consistent in the results it produces and often produces extraneous changes
- The reflection stage doesn't understand git diffs well so it okays bogus changes often.
