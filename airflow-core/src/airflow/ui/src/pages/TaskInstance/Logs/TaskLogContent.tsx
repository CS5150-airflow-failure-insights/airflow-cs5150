/*!
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
import { Box, Code, VStack, IconButton, Textarea, Text, Button, HStack, Link } from "@chakra-ui/react";
import { useMutation } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import axios from "axios";
import { isValidElement, useLayoutEffect, useRef, useState, useCallback, useMemo } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useTranslation } from "react-i18next";
import { FiBookOpen, FiChevronDown, FiChevronUp, FiEdit2, FiExternalLink } from "react-icons/fi";



import { useAuthLinksServiceGetCurrentUserInfo } from "openapi/queries";
import DeleteDialog from "src/components/DeleteDialog";
import { ErrorAlert } from "src/components/ErrorAlert";
import { Dialog, ProgressBar, Tooltip, toaster } from "src/components/ui";
import { getMetaKey } from "src/utils";



import { scrollToBottom, scrollToTop } from "./utils";


type Props = {
  readonly error: unknown;
  readonly isLoading: boolean;
  readonly logError: unknown;
  readonly parsedLogs: Array<JSX.Element | string | undefined>;
  readonly wrap: boolean;
};

// Shape of error notes returned by the API (includes signature for regex matching)
type UiErrorNote = {
  note_id: number;
  author: string;
  note_text: string;
  external_url: string | null;
  signature_regex: string; // for regex matching
  signature_canonical: string; // what the error looks like
};

type UiErrorNoteUpdate = Pick<UiErrorNote, "note_id" | "author" | "note_text" | "external_url">;

// TODO(backend): Replace all MOCK_* constants with a list of error-note records fetched from API.
// Expected future shape (example): { id, signature, triggerLine, matchedErrorText, author, description }

const extractTextFromNode = (node: unknown): string => {
  if (node === undefined || node === null || typeof node === "boolean") {
    return "";
  }

  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }

  if (Array.isArray(node)) {
    const parts = node
      .map((child) => extractTextFromNode(child))
      .filter((text) => text.length > 0);

    const result = parts.reduce((acc, part, i) => {
      if (i === 0) return part;
      // Don't add space before punctuation
      const startsWithPunctuation = /^[.:,!?;)\]}]/.test(part);
      return acc + (startsWithPunctuation ? "" : " ") + part;
    }, "");
    return result;
  }

  if (!isValidElement(node)) {
    return "";
  }

  const { children } = node.props as { children?: unknown };

  return extractTextFromNode(children);
};

const getLogEntryText = (entry: JSX.Element | string | undefined): string => {
  if (entry === undefined) {
    return "";
  }

  if (typeof entry === "string") {
    return entry;
  }

  return extractTextFromNode(entry);
};

const ScrollToButton = ({
  direction,
  onClick,
}: {
  readonly direction: "bottom" | "top";
  readonly onClick: () => void;
}) => {
  const { t: translate } = useTranslation("common");

  return (
    <Tooltip
      closeDelay={100}
      content={translate("scroll.tooltip", {
        direction: translate(`scroll.direction.${direction}`),
        hotkey: `${getMetaKey()}+${direction === "bottom" ? "↓" : "↑"}`,
      })}
      openDelay={100}
    >
      <IconButton
        _ltr={{
          left: "auto",
          right: 4,
        }}
        _rtl={{
          left: 4,
          right: "auto",
        }}
        aria-label={translate(`scroll.direction.${direction}`)}
        bg="bg.panel"
        bottom={direction === "bottom" ? 4 : 14}
        onClick={onClick}
        position="absolute"
        rounded="full"
        size="xs"
        variant="outline"
      >
        {direction === "bottom" ? <FiChevronDown /> : <FiChevronUp />}
      </IconButton>
    </Tooltip>
  );
};

export const TaskLogContent = ({ error, isLoading, logError, parsedLogs, wrap }: Props) => {
  const hash = location.hash.replace("#", "");
  const parentRef = useRef<HTMLDivElement | null>(null);

  // MOCK ERROR NOTES
  // const [notes, setNotes] = useState<UiErrorNote[]>([
  //   {
  //     id: 1,
  //     author: "katie",
  //     highlightedText:
  //       "KeyError: 'SNOWFLAKE_ACCOUNT' File \".../airflow/models/variable.py\", line 176, in get raise KeyError(key) KeyError: 'SNOWFLAKE_ACCOUNT'",
  //     noteText: "Example troubleshooting note 1.",
  //     externalUrl: "https://airflow.apache.org/docs/apache-airflow/stable/howto/variable.html",
  //   },
  //   {
  //     id: 2,
  //     author: "admin",
  //     highlightedText: `ERROR - sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) FATAL:  password authentication failed for user "analytics_user"`,
  //     noteText: "Example troubleshooting note 2.",
  //     externalUrl: "https://airflow.apache.org/docs/apache-airflow/stable/howto/variable.html",
  //   },
  // ]);

  // Error notes fetched from API
  const [notes, setNotes] = useState<UiErrorNote[]>([]);

  // Fetch error notes on component mount
  useLayoutEffect(() => {
    const fetchErrorNotes = async () => {
      try {
        const response = await axios.get("/ui/error-notes");
        if (response.data.notes) {
          setNotes(response.data.notes);
        }
      } catch (error) {
        // Failed to fetch error notes, continue with empty list
      }
    };

    fetchErrorNotes();
  }, []);

  // ── Annotate-on-highlight state ────────────────────────────────────────
  const [selectedText, setSelectedText] = useState<string>("");
  const [buttonPos, setButtonPos] = useState<{ x: number; y: number } | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isKnowledgeModalOpen, setIsKnowledgeModalOpen] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [noteURL, setNoteURL] = useState("");
  const { data: currentUser } = useAuthLinksServiceGetCurrentUserInfo();

  const { isPending: isSavingNote, mutate: saveNote } = useMutation({
    mutationFn: async ({
      highlightedText,
      note,
      external_url,
    }: {
      highlightedText: string;
      note: string;
      external_url: string | null;
    }) =>
      axios.post("/ui/error-notes", {
        external_url: external_url,
        highlighted_text: highlightedText,
        note_text: note,
      }),
    onError: () => {
      toaster.create({
        description: "The note could not be saved.",
        title: "Save failed",
        type: "error",
      });
    },
    onSuccess: () => {
      toaster.create({
        description: "The error note was saved.",
        title: "Note saved",
        type: "success",
      });
      setIsModalOpen(false);
      setSelectedText("");
      setNoteText("");
      window.getSelection()?.removeAllRanges();
      window.location.reload();
    },
  });

  const matchingNotesByLineIndex = useMemo(() => {
    const matches = new Map<number, UiErrorNote[]>();

    // Regex to match and remove timestamps from log entries (various formats)
    // Matches: [2026-04-20 13:03:56], 2026-04-20 13:03:56, 2026-04-20T13:03:56, etc.
    const timestampRegex =
      /\[\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:\d{2})?)?\]\s*|\b\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:\d{2})?)?\b/g;

    parsedLogs.forEach((entry, index) => {
      const rawText = getLogEntryText(entry);
      let cleanText = rawText.replace(/^\d+\s*\[\s*\]\s*/, "");
      let logText = cleanText.replace(/\s+/g, " ").trim();

      // Remove timestamps from log text to match error notes (timestamps are stripped during signature creation)
      logText = logText.replace(timestampRegex, "").replace(/\s+/g, " ").trim();

      const matchedNotes = notes.filter((note) => {
        try {
          const regex = new RegExp(note.signature_regex);
          let testResult = regex.test(logText);

          // If no match and the regex starts with escaped punctuation (like \]),
          // try matching without that leading punctuation (handles selection artifacts)
          if (!testResult && /^\\[\\.\[\](){}\-+*?^$|]/.test(note.signature_regex.substring(0, 3))) {
            // Remove leading escaped punctuation from regex pattern
            const cleanedRegexPattern = note.signature_regex.replace(/^\\[\\.\[\](){}\-+*?^$|]+/, "");
            if (cleanedRegexPattern && cleanedRegexPattern !== note.signature_regex) {
              const cleanedRegex = new RegExp(cleanedRegexPattern);
              testResult = cleanedRegex.test(logText);
            }
          }

          return testResult;
        } catch (e) {
          return false;
        }
      });

      if (matchedNotes.length > 0) {
        matches.set(index, matchedNotes);
      }
    });

    return matches;
  }, [parsedLogs, notes]);

  const handleMouseUp = useCallback(() => {
    const selection = window.getSelection();
    const text = selection?.toString().trim() ?? "";

    if (!text || !parentRef.current) {
      setButtonPos(null);
      setSelectedText("");
      return;
    }

    // Only show the icon if the selection is inside our log container
    const range = selection?.getRangeAt(0);
    if (!range || !parentRef.current.contains(range.commonAncestorContainer)) {
      setButtonPos(null);
      setSelectedText("");
      return;
    }

    // Check that selection is within a single log line (same data-index)
    // Find the log line container for the start and end of the selection
    const getLogLineIndex = (node: Node): string | null => {
      // Start from the node - if it's a text node, use its parent
      let current: Node | null = node.nodeType === Node.TEXT_NODE ? node.parentNode : node;

      while (current && current !== parentRef.current) {
        if (current.nodeType === Node.ELEMENT_NODE) {
          const element = current as Element;
          const index = element.getAttribute("data-index");
          if (index !== null) {
            return index;
          }
        }
        current = current.parentNode;
      }
      return null;
    };

    const startIndex = getLogLineIndex(range.startContainer);
    const endIndex = getLogLineIndex(range.endContainer);

    // Handle three cases:
    // 1. Both found with same index - allow (normal case)
    // 2. Both found with different index - reject (crosses log lines)
    // 3. One or both null - allow if within container (likely nested in link/element without data-index)
    const bothFoundAndDifferent = startIndex !== null && endIndex !== null && startIndex !== endIndex;
    const neitherFound = startIndex === null && endIndex === null;
    const shouldAllow = !bothFoundAndDifferent;

    if (!shouldAllow) {
      setButtonPos(null);
      setSelectedText("");
      toaster.create({
        description: "Please select text within a single log line.",
        title: "Selection spans multiple lines",
        type: "warning",
      });
      return;
    }

    const rect = range.getBoundingClientRect();

    // Position the button near the end of selection, but keep it visible in viewport
    let buttonX = rect.right + 6;
    const viewportWidth = window.innerWidth;
    const buttonWidth = 32; // Approximate width of the icon button
    const rightMargin = 10;

    // If button would go off-screen to the right, position it at the left side instead
    if (buttonX + buttonWidth > viewportWidth - rightMargin) {
      buttonX = Math.max(10, rect.left - buttonWidth - 6);
    }

    setButtonPos({ x: buttonX, y: rect.top - 4 });
    setSelectedText(text);
  }, []);

  const handleOpenModal = () => {
    setNoteText("");
    setIsModalOpen(true);
    // The floating button disappears once the modal opens
    setButtonPos(null);
  };

  const handleSubmitNote = () => {
    const trimmedNote = noteText.trim();
    let trimmedSelection = selectedText.trim();

    // Strip line number and bracket prefix from selection (e.g., "11 [ ]")
    trimmedSelection = trimmedSelection.replace(/^\d+\s*\[\s*\]\s*/, "");

    if (!trimmedNote || !trimmedSelection) {
      toaster.create({
        description: "Missing note text or selected log text.",
        title: "Cannot save note",
        type: "error",
      });
      return;
    }

    saveNote({
      highlightedText: trimmedSelection,
      note: trimmedNote,
      external_url: noteURL.trim() || null,
    });
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setSelectedText("");
    setNoteText("");
    setNoteURL("");
    window.getSelection()?.removeAllRanges();
  };
  // ──────────────────────────────────────────────────────────────────────

  const rowVirtualizer = useVirtualizer({
    count: parsedLogs.length,
    estimateSize: () => 20,
    getScrollElement: () => parentRef.current,
    overscan: 10,
  });

  const contentHeight = rowVirtualizer.getTotalSize();
  const containerHeight = rowVirtualizer.scrollElement?.clientHeight ?? 0;
  const showScrollButtons = parsedLogs.length > 1 && contentHeight > containerHeight;

  useLayoutEffect(() => {
    if (location.hash && !isLoading) {
      rowVirtualizer.scrollToIndex(Math.min(Number(hash) + 5, parsedLogs.length - 1));
    }
  }, [isLoading, rowVirtualizer, hash, parsedLogs]);

  const handleScrollTo = (to: "bottom" | "top") => {
    if (parsedLogs.length === 0) {
      return;
    }

    const el = rowVirtualizer.scrollElement ?? parentRef.current;

    if (!el) {
      return;
    }

    if (to === "top") {
      scrollToTop({ element: el, virtualizer: rowVirtualizer });
    } else {
      scrollToBottom({ element: el, virtualizer: rowVirtualizer });
    }
  };

  useHotkeys("mod+ArrowDown", () => handleScrollTo("bottom"), { enabled: !isLoading });
  useHotkeys("mod+ArrowUp", () => handleScrollTo("top"), { enabled: !isLoading });

  // When multiple notes match the same line, we pick the best one to show in the tooltip/modal.
  const [activeMatchedNote, setActiveMatchedNote] = useState<UiErrorNote | null>(null);
  const [activeMatchedLineIndex, setActiveMatchedLineIndex] = useState<number | null>(null);
  const [isEditingMatchedNote, setIsEditingMatchedNote] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [editedMatchedNoteText, setEditedMatchedNoteText] = useState("");
  const [editedMatchedNoteUrl, setEditedMatchedNoteUrl] = useState("");
  const currentUsername = currentUser?.username?.trim() ?? "";
  const canEditActiveMatchedNote =
    Boolean(currentUsername) &&
    Boolean(activeMatchedNote?.author) &&
    currentUsername === activeMatchedNote?.author;

  const { isPending: isUpdatingMatchedNote, mutate: updateMatchedNote } = useMutation({
    mutationFn: async ({
      noteId,
      noteText,
      externalUrl,
    }: {
      noteId: number;
      noteText: string;
      externalUrl: string | null;
    }) =>
      axios.patch(`/ui/error-notes/${noteId}`, {
        note_text: noteText,
        external_url: externalUrl,
      }),
    onError: (error: unknown) => {
      const status = axios.isAxiosError(error) ? error.response?.status : undefined;
      toaster.create({
        description:
          status === 403
            ? "Only the note author can edit this note."
            : "The note could not be updated.",
        title: "Update failed",
        type: "error",
      });
    },
    onSuccess: (response) => {
      const updatedNote = response.data as UiErrorNoteUpdate;
      setNotes((existing) =>
        existing.map((note) => (note.note_id === updatedNote.note_id ? { ...note, ...updatedNote } : note)),
      );
      setActiveMatchedNote((current) =>
        current && current.note_id === updatedNote.note_id ? { ...current, ...updatedNote } : current,
      );
      setEditedMatchedNoteText(updatedNote.note_text);
      setEditedMatchedNoteUrl(updatedNote.external_url ?? "");
      setIsEditingMatchedNote(false);
      toaster.create({
        description: "The error note was updated.",
        title: "Note updated",
        type: "success",
      });
      window.location.reload();
    },
  });

  const { isPending: isDeletingMatchedNote, mutate: deleteMatchedNote } = useMutation({
    mutationFn: async ({ noteId }: { noteId: number }) => axios.delete(`/ui/error-notes/${noteId}`),
    onError: (error: unknown) => {
      const status = axios.isAxiosError(error) ? error.response?.status : undefined;
      toaster.create({
        description:
          status === 403
            ? "Only the note author can delete this note."
            : "The note could not be deleted.",
        title: "Delete failed",
        type: "error",
      });
    },
    onSuccess: () => {
      toaster.create({
        description: "The error note was deleted.",
        title: "Note deleted",
        type: "success",
      });
      window.location.reload();
    },
  });

  const pickBestMatchedNote = (matchedNotes: UiErrorNote[]): UiErrorNote | null => {
    if (matchedNotes.length === 0) {
      return null;
    }

    // Prefer the most specific signature (longest canonical form), with note_id as tiebreaker
    const sorted = [...matchedNotes].sort((a, b) => {
      const lengthDiff = b.signature_canonical.length - a.signature_canonical.length;
      if (lengthDiff !== 0) return lengthDiff;
      return b.note_id - a.note_id;
    });

    return sorted[0] ?? null;
  }

  const handleOpenMatchedNote = (lineIndex: number) => {
    const matchedNotes = matchingNotesByLineIndex.get(lineIndex) ?? [];
    const bestMatch = pickBestMatchedNote(matchedNotes);

    if (!bestMatch) {
      return;
    }

    setActiveMatchedLineIndex(lineIndex);
    setActiveMatchedNote(bestMatch);
    setEditedMatchedNoteText(bestMatch.note_text);
    setEditedMatchedNoteUrl(bestMatch.external_url ?? "");
    setIsEditingMatchedNote(false);
    setIsKnowledgeModalOpen(true);
  };

  const handleCloseKnowledgeModal = () => {
    setIsKnowledgeModalOpen(false);
    setActiveMatchedLineIndex(null);
    setActiveMatchedNote(null);
    setEditedMatchedNoteText("");
    setEditedMatchedNoteUrl("");
    setIsEditingMatchedNote(false);
    setIsDeleteConfirmOpen(false);
  };

  return (
    <Box display="flex" flexDirection="column" flexGrow={1} h="100%" minHeight={0} position="relative">
      <ErrorAlert error={error ?? logError} />
      <ProgressBar size="xs" visibility={isLoading ? "visible" : "hidden"} />
      <Box px={3} py={2} bg="gray.50" fontSize="xs" color="gray.600" borderBottom="1px solid" borderColor="gray.200">
        💡 Highlight any log line to add an error note for your team
      </Box>
      <Box
        data-testid="virtual-scroll-container"
        flexGrow={1}
        minHeight={0}
        onMouseUp={handleMouseUp}
        overflow="auto"
        position="relative"
        py={3}
        ref={parentRef}
        width="100%"
      >
        <Code
          css={{
            "& *::selection": { bg: "blue.emphasized" },
          }}
          data-testid="virtualized-list"
          display="block"
          textWrap={wrap ? "pre" : "nowrap"}
          width="100%"
        >
          <VStack
            alignItems="flex-start"
            gap={0}
            h={`${rowVirtualizer.getTotalSize()}px`}
            position="relative"
          >
            {rowVirtualizer.getVirtualItems().map((virtualRow) => (
              <Box
                _ltr={{ left: 0, right: "auto" }}
                _rtl={{ left: "auto", right: 0 }}
                _hover={{ bg: "blue.50", cursor: "text" }}
                bgColor={
                  Boolean(hash) && virtualRow.index === Number(hash) - 1 ? "brand.emphasized" : "transparent"
                }
                data-index={virtualRow.index}
                data-testid={`virtualized-item-${virtualRow.index}`}
                key={virtualRow.key}
                position="absolute"
                ref={rowVirtualizer.measureElement}
                top={0}
                transform={`translateY(${virtualRow.start}px)`}
                width={wrap ? "100%" : "max-content"}
              >
                <HStack alignItems="flex-start" gap={0}>
                  {(matchingNotesByLineIndex.get(virtualRow.index)?.length ?? 0) > 0 ? (
                    <Box position="relative" zIndex={10} color="white">
                      <Tooltip content="View Error Note" openDelay={100} portalled>
                        <Box
                        as="button"
                        onClick={() => handleOpenMatchedNote(virtualRow.index)}
                        display="inline-flex"
                        alignItems="center"
                        gap={0.5}
                        px={1}
                        py={0}
                        mr={0}
                        bg="red.100"
                        borderRadius="xs"
                        fontSize="2xs"
                        fontWeight="semibold"
                        color="red.700"
                        border="none"
                        cursor="pointer"
                        _hover={{ bg: "red.200" }}
                        _active={{ bg: "red.300" }}
                        title="View error note"
                      >
                        <FiBookOpen size={12} />
                        <Text fontSize="2xs">Fix</Text>
                      </Box>
                      </Tooltip>
                    </Box>
                  ) : undefined}
                  <Box>{parsedLogs[virtualRow.index] ?? undefined}</Box>
                </HStack>
              </Box>
            ))}
          </VStack>
        </Code>
      </Box>

      {showScrollButtons ? (
        <>
          <ScrollToButton direction="top" onClick={() => handleScrollTo("top")} />
          <ScrollToButton direction="bottom" onClick={() => handleScrollTo("bottom")} />
        </>
      ) : undefined}

      {/* Floating annotate icon — appears at the end of a text selection */}
      {buttonPos !== null && (
        <IconButton
          aria-label="Add error note"
          bg="bg.panel"
          border="1px solid"
          borderColor="border.emphasized"
          boxShadow="sm"
          left={`${buttonPos.x}px`}
          onClick={handleOpenModal}
          position="fixed"
          rounded="md"
          size="xs"
          title="Add error note"
          top={`${buttonPos.y}px`}
          zIndex={1500}
          color={"black"}
        >
          <FiEdit2 />
        </IconButton>
      )}

      {/* Error note modal */}
      <Dialog.Root onOpenChange={handleCloseModal} open={isModalOpen} size="md">
        <Dialog.Content>
          <Dialog.Header>
            <Text fontSize="lg" fontWeight="semibold">
              Add Error Note
            </Text>
          </Dialog.Header>
          <Dialog.CloseTrigger />

          <Dialog.Body display="flex" flexDirection="column" gap={3}>
            <Box>
              <Text fontSize="xs" fontWeight="medium" mb={1} textTransform="uppercase">
                Highlighted text
              </Text>
              <Code
                borderRadius="md"
                display="block"
                fontSize="xs"
                maxH="100px"
                overflowY="auto"
                p={2}
                whiteSpace="pre-wrap"
                wordBreak="break-all"
              >
                {selectedText}
              </Code>
            </Box>

            <Box>
              <Text fontSize="xs" fontWeight="medium" mb={1} textTransform="uppercase">
                Note
              </Text>
              <Textarea
                autoFocus
                onChange={(e) => setNoteText(e.target.value)}
                placeholder="Describe this error and how to fix it…"
                rows={5}
                value={noteText}
              />
            </Box>
            <Box>
              <Text fontSize="xs" fontWeight="medium" mb={1} textTransform="uppercase">
                Reference Documentation Link
              </Text>
              <Textarea
                onChange={(e) => setNoteURL(e.target.value)}
                placeholder="https://example.com/docs"
                rows={1}
                value={noteURL}
              />
            </Box>
          </Dialog.Body>

          <Dialog.Footer>
            <HStack gap={2} justifyContent="flex-end">
              <Button onClick={handleCloseModal} variant="outline">
                Cancel
              </Button>
              <Button
                colorPalette="blue"
                disabled={(!noteText.trim() && !noteURL.trim()) || isSavingNote}
                onClick={handleSubmitNote}
              >
                Save Note
              </Button>
            </HStack>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Root>

      <Dialog.Root onOpenChange={handleCloseKnowledgeModal} open={isKnowledgeModalOpen} size="md">
        <Dialog.Content>
          <Dialog.Header pb={4}>
            <HStack gap={2} alignItems="center">
              <FiBookOpen size={20} />
              <Text fontSize="lg" fontWeight="bold">
                Error Note
              </Text>
            </HStack>
          </Dialog.Header>
          <Dialog.CloseTrigger />

          <Dialog.Body display="flex" flexDirection="column" gap={4}>
            {/* Matched Error Section */}
            <Box borderRadius="md" bg="gray.50" p={3}>
              <Text fontSize="xs" fontWeight="semibold" textTransform="uppercase" color="gray.600" mb={2}>
                Matched Error
              </Text>
              <Code
                borderRadius="sm"
                display="block"
                fontSize="sm"
                maxH="140px"
                overflowY="auto"
                p={2.5}
                whiteSpace="pre-wrap"
                wordBreak="break-word"
                bg="white"
                borderLeft="3px solid"
                borderColor="red.400"
              >
                {activeMatchedNote?.signature_canonical ?? "-"}
              </Code>
            </Box>

            {/* Author & Metadata Row */}
            <Box display="flex" gap={4}>
              <Box flex={1}>
                <Text fontSize="xs" fontWeight="semibold" textTransform="uppercase" color="gray.600" mb={1}>
                  Author
                </Text>
                <Text fontSize="sm" fontWeight="medium">
                  {activeMatchedNote?.author ?? "-"}
                </Text>
              </Box>
              {activeMatchedLineIndex !== null ? (
                <Box flex={1}>
                  <Text fontSize="xs" fontWeight="semibold" textTransform="uppercase" color="gray.600" mb={1}>
                    Log Line
                  </Text>
                  <Text fontSize="sm" fontWeight="medium">
                    {activeMatchedLineIndex + 1}
                  </Text>
                </Box>
              ) : null}
            </Box>

            {/* Note Content Section */}
            <Box>
              <Text fontSize="xs" fontWeight="semibold" textTransform="uppercase" color="gray.600" mb={2}>
                Resolution
              </Text>
              {isEditingMatchedNote ? (
                <Textarea
                  onChange={(event) => setEditedMatchedNoteText(event.target.value)}
                  rows={5}
                  value={editedMatchedNoteText}
                />
              ) : (
                <Text fontSize="sm" lineHeight="1.6" color="gray.800">
                  {activeMatchedNote?.note_text ?? "-"}
                </Text>
              )}
            </Box>

            {/* Reference Documentation Section */}
            <Box>
              <Text fontSize="xs" fontWeight="semibold" textTransform="uppercase" color="gray.600" mb={2}>
                Reference Documentation
              </Text>
              {isEditingMatchedNote ? (
                <Textarea
                  onChange={(event) => setEditedMatchedNoteUrl(event.target.value)}
                  placeholder="https://example.com/docs"
                  rows={1}
                  value={editedMatchedNoteUrl}
                />
              ) : activeMatchedNote?.external_url ? (
                <Box borderRadius="md" bg="blue.50" p={3} borderLeft="3px solid" borderColor="blue.400">
                  <Link
                    href={activeMatchedNote.external_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    color="blue.600"
                    fontSize="sm"
                    fontWeight="medium"
                    display="flex"
                    alignItems="center"
                    gap={1}
                    _hover={{ textDecoration: "underline", opacity: 0.8 }}
                    wordBreak="break-all"
                  >
                    {activeMatchedNote.external_url}
                    <FiExternalLink size={14} />
                  </Link>
                </Box>
              ) : (
                <Text fontSize="sm" color="gray.500">
                  No reference documentation link.
                </Text>
              )}
            </Box>
          </Dialog.Body>

          <Dialog.Footer pt={4} borderTop="1px solid" borderColor="gray.200">
            <HStack gap={2} justifyContent="flex-end">
              {canEditActiveMatchedNote && !isEditingMatchedNote ? (
                <Button onClick={() => setIsEditingMatchedNote(true)} variant="outline">
                  Edit
                </Button>
              ) : null}
              {canEditActiveMatchedNote && isEditingMatchedNote ? (
                <Button
                  colorPalette="blue"
                  disabled={!editedMatchedNoteText.trim() || isUpdatingMatchedNote || isDeletingMatchedNote}
                  onClick={() => {
                    if (activeMatchedNote === null) {
                      return;
                    }
                    updateMatchedNote({
                      noteId: activeMatchedNote.note_id,
                      noteText: editedMatchedNoteText.trim(),
                      externalUrl: editedMatchedNoteUrl.trim() || null,
                    });
                  }}
                >
                  Save
                </Button>
              ) : null}
              {canEditActiveMatchedNote && isEditingMatchedNote ? (
                <Button
                  disabled={isUpdatingMatchedNote || isDeletingMatchedNote}
                  onClick={() => {
                    setEditedMatchedNoteText(activeMatchedNote?.note_text ?? "");
                    setEditedMatchedNoteUrl(activeMatchedNote?.external_url ?? "");
                    setIsEditingMatchedNote(false);
                  }}
                  variant="outline"
                >
                  Cancel Edit
                </Button>
              ) : null}
              {canEditActiveMatchedNote && !isEditingMatchedNote ? (
                <Button
                  colorPalette="red"
                  disabled={isUpdatingMatchedNote || isDeletingMatchedNote}
                  onClick={() => setIsDeleteConfirmOpen(true)}
                  variant="outline"
                >
                  Delete
                </Button>
              ) : null}
              <Button onClick={handleCloseKnowledgeModal} variant="outline">
                Close
              </Button>
            </HStack>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Root>
      <DeleteDialog
        isDeleting={isDeletingMatchedNote}
        onClose={() => setIsDeleteConfirmOpen(false)}
        onDelete={() => {
          if (activeMatchedNote === null) {
            return;
          }
          deleteMatchedNote({ noteId: activeMatchedNote.note_id });
        }}
        open={isDeleteConfirmOpen}
        resourceName="error note"
        title="Delete Error Note"
        warningText="This action cannot be undone."
      />
    </Box>
  );
}