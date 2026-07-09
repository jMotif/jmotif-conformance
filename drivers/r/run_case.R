#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(jsonlite)
  library(jmotif)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) {
  stop("usage: run_case.R <case.json>", call. = FALSE)
}

repo_root <- Sys.getenv("JMOTIF_CONFORMANCE_ROOT", unset = normalizePath("."))
case <- fromJSON(args[1], simplifyVector = FALSE)

load_series <- function(case, root) {
  path <- file.path(root, case$series)
  values <- scan(path, quiet = TRUE)
  slice <- case$slice
  start <- if (is.null(slice[[1]])) 1L else as.integer(slice[[1]]) + 1L
  end <- if (is.null(slice[[2]])) length(values) else as.integer(slice[[2]])
  values[start:end]
}

nr_strategy_r <- function(value) tolower(value)

load_sax_string <- function(case, root) {
  if (!is.null(case[["sax_string"]])) {
    return(trimws(case[["sax_string"]]))
  }
  if (is.null(case[["sax_string_file"]])) {
    stop("case requires sax_string or sax_string_file", call. = FALSE)
  }
  path <- file.path(root, case[["sax_string_file"]])
  text <- paste(readLines(path, warn = FALSE), collapse = " ")
  return(trimws(gsub("\\s+", " ", text)))
}

repair_rules_from_grammar <- function(grammar) {
  rules <- lapply(seq_along(grammar), function(i) {
    rec <- grammar[[i]]
    rid <- as.integer(sub("^R", "", as.character(rec$rule_name)[1]))
    list(
      rule_id = rid,
      rule_string = as.character(rec$rule_string)[1],
      expanded_rule_string = as.character(rec$expanded_rule_string)[1]
    )
  })
  r0 <- Filter(function(r) r$rule_id == 0L, rules)[[1]]
  r0_rule <- r0$rule_string
  r0_expanded <- r0$expanded_rule_string
  list(
    input = r0_expanded,
    r0_rule_string = trimws(r0_rule),
    decompressed = trimws(r0_expanded),
    r0_no_repeated_digram = r0_no_repeated_digram(r0_rule),
    rules = rules
  )
}

r0_no_repeated_digram <- function(r0_rule_string) {
  text <- trimws(as.character(r0_rule_string)[1])
  if (!nzchar(text)) {
    return(TRUE)
  }
  tokens <- strsplit(text, "\\s+")[[1]]
  if (length(tokens) < 2) {
    return(TRUE)
  }
  digrams <- paste(tokens[-length(tokens)], tokens[-1], sep = " ")
  !any(duplicated(digrams))
}

run_case <- function(case, root) {
  op <- case$operation
  params <- case$params

  if (op == "repair") {
    sax_string <- load_sax_string(case, root)
    grammar <- str_to_repair_grammar(sax_string)
    result <- repair_rules_from_grammar(grammar)
    result$input <- sax_string
    return(result)
  }

  series <- load_series(case, root)

  if (op == "discord_bruteforce") {
    discords <- find_discords_brute_force(
      series,
      params$window,
      params$num_discords,
      params$threshold
    )
    rows <- lapply(seq_len(nrow(discords)), function(i) {
      list(
        position = as.integer(discords$position[i]),
        nn_distance = as.numeric(discords$nn_distance[i])
      )
    })
    return(list(discords = rows))
  }

  if (op == "discord_hotsax") {
    discords <- find_discords_hotsax(
      series,
      params$window,
      params$paa,
      params$alphabet,
      params$threshold,
      params$num_discords
    )
    rows <- lapply(seq_len(nrow(discords)), function(i) {
      list(
        position = as.integer(discords$position[i]),
        nn_distance = as.numeric(discords$nn_distance[i])
      )
    })
    return(list(discords = rows))
  }

  if (op == "sax_via_window") {
    sax <- sax_via_window(
      series,
      params$window,
      params$paa,
      params$alphabet,
      nr_strategy_r(params$nr_strategy),
      params$threshold
    )
    windows <- lapply(params$pinned_indices, function(index) {
      idx <- as.character(index)
      list(index = as.integer(index), word = sax[[idx]])
    })
    return(list(sax_windows = windows))
  }

  stop("unsupported operation: ", op, call. = FALSE)
}

result <- run_case(case, repo_root)
cat(toJSON(result, auto_unbox = TRUE, digits = 16, pretty = FALSE))
