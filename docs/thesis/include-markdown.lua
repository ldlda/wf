-- Replace explicit include markers with parsed Markdown before cross-reference processing.
local agent_results_path = nil

local function read_metadata(meta)
  if meta.thesisAgentResults then
    agent_results_path = pandoc.utils.stringify(meta.thesisAgentResults)
  end
  return meta
end

local function include_results(div)
  if div.identifier ~= "include-agent-challenge-results" then
    return nil
  end
  if not agent_results_path or agent_results_path == "" then
    error("thesisAgentResults metadata is required for the evaluation include")
  end

  local file, open_error = io.open(agent_results_path, "r")
  if not file then
    error("cannot open agent challenge results: " .. tostring(open_error))
  end
  local content = file:read("*a")
  file:close()
  return pandoc.read(content, "markdown").blocks
end

-- Separate passes guarantee metadata is available before block traversal.
return {
  { Meta = read_metadata },
  { Div = include_results },
}
