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

load_ucr_data <- function(path) {
  data <- list()
  lines <- readLines(path, warn = FALSE)
  for (line in lines) {
    line <- trimws(line)
    if (!nzchar(line)) {
      next
    }
    parts <- strsplit(gsub(",", " ", line), "\\s+")[[1]]
    parts <- parts[nzchar(parts)]
    if (length(parts) < 2) {
      next
    }
    label <- parts[[1]]
    label_num <- suppressWarnings(as.numeric(label))
    if (!is.na(label_num)) {
      label <- as.character(as.integer(round(label_num)))
    }
    values <- as.numeric(parts[-1])
    if (is.null(data[[label]])) {
      data[[label]] <- list(values)
    } else {
      data[[label]] <- c(data[[label]], list(values))
    }
  }
  data
}

saxvsm_predict_label <- function(bag, tfidf) {
  cosines <- cosine_sim(list(bag = bag, tfidf = tfidf))
  vals <- cosines$cosines
  if (length(unique(vals)) <= 1) {
    return(NA_character_)
  }
  cosines$classes[[which.max(vals)]]
}

run_saxvsm_classify <- function(case, root) {
  params <- case$params
  train <- load_ucr_data(file.path(root, case$train))
  test <- load_ucr_data(file.path(root, case$test))
  nr <- nr_strategy_r(params$nr_strategy)
  class_name <- function(label) paste0("c", label)
  bags <- setNames(
    lapply(names(train), function(label) {
      mat <- do.call(rbind, train[[label]])
      manyseries_to_wordbag(
        mat,
        params$window,
        params$paa,
        params$alphabet,
        nr,
        params$threshold
      )
    }),
    vapply(names(train), class_name, character(1))
  )
  tfidf <- bags_to_tfidf(bags)
  correct <- 0L
  total <- 0L
  for (label in names(test)) {
    for (series in test[[label]]) {
      total <- total + 1L
      bag <- series_to_wordbag(
        series,
        params$window,
        params$paa,
        params$alphabet,
        nr,
        params$threshold
      )
      predicted <- saxvsm_predict_label(bag, tfidf)
      if (!is.na(predicted)) {
        predicted <- sub("^c", "", predicted)
      }
      if (!is.na(predicted) && identical(predicted, label)) {
        correct <- correct + 1L
      }
    }
  }
  accuracy <- if (total == 0L) 0 else correct / total
  list(
    accuracy = accuracy,
    error = 1 - accuracy,
    correct = correct,
    total = total
  )
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

  if (op == "saxvsm_classify") {
    return(run_saxvsm_classify(case, root))
  }

  series <- load_series(case, root)

  if (op == "rra_discord") {
    seed <- if (is.null(params$seed)) -1L else as.integer(params$seed)
    discords <- find_discords_rra(
      series,
      params$window,
      params$paa,
      params$alphabet,
      nr_strategy_r(params$nr_strategy),
      params$threshold,
      params$num_discords,
      seed
    )
    if (nrow(discords) < 1) {
      stop("RRA found no discords", call. = FALSE)
    }
    hot <- find_discords_hotsax(
      series,
      params$window,
      params$paa,
      params$alphabet,
      params$threshold,
      1L
    )
    return(list(
      top_discord = list(
        start = as.integer(discords$start[1]),
        end = as.integer(discords$end[1])
      ),
      hotsax_top_position = as.integer(hot$position[1])
    ))
  }

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
