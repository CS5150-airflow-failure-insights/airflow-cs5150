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
import { Box, Code, VStack, IconButton, Textarea, Text, Button, HStack } from "@chakra-ui/react";
import { useMutation } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import axios from "axios";
import { isValidElement, useLayoutEffect, useRef, useState, useCallback, useMemo } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useTranslation } from "react-i18next";
import { FiBookOpen, FiChevronDown, FiChevronUp, FiEdit2, FiTrash2, FiExternalLink } from "react-icons/fi";

import { useAuthLinksServiceGetCurrentUserInfo } from "openapi/queries";
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

// TODO(backend): Define the shape of error notes returned by the API and replace this with a real type import.
type UiErrorNote = {
  id: number;
  author: string;
  highlightedText: string;
  noteText: string;
  externalUrl: string | null;
};

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
    return node.map((child) => extractTextFromNode(child)).join("");
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

// Normalizes text so matching is stable across whitespace/newline differences in logs.
const normalizeForMatch = (text: string): string =>
  text
    .toLowerCase()
    .replace(/\s+/g, " ") // collapse whitespace/newlines/tabs
    .trim();

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
  const [notes, setNotes] = useState<UiErrorNote[]>([
    {
      id: 1,
      author: "katie",
      highlightedText:
        "KeyError: 'SNOWFLAKE_ACCOUNT' File \".../airflow/models/variable.py\", line 176, in get raise KeyError(key) KeyError: 'SNOWFLAKE_ACCOUNT'",
      noteText: "Example troubleshooting note 1.",
      externalUrl: "https://airflow.apache.org/docs/apache-airflow/stable/howto/variable.html",
    },
    {
      id: 2,
      author: "admin",
      highlightedText: `ERROR - sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) FATAL:  password authentication failed for user "analytics_user"`,
      noteText: "Example troubleshooting note 2.",
      externalUrl: "https://airflow.apache.org/docs/apache-airflow/stable/howto/variable.html",
    },
  ]);

  // ── Annotate-on-highlight state ────────────────────────────────────────
  const [selectedText, setSelectedText] = useState<string>("");
  const [buttonPos, setButtonPos] = useState<{ x: number; y: number } | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isKnowledgeModalOpen, setIsKnowledgeModalOpen] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [noteURL, setNoteURL] = useState("");
  const { data: currentUser } = useAuthLinksServiceGetCurrentUserInfo();

  // for get use axios.get("u"i/error-note/lookup")

  const { isPending: isSavingNote, mutate: saveNote } = useMutation({
    mutationFn: async ({
      author,
      highlightedText,
      note,
      external_url,
    }: {
      author: string;
      highlightedText: string;
      note: string;
      external_url: string | null;
    }) =>
      axios.post("/ui/error-notes", {
        author,
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
    },
  });

  const matchingNotesByLineIndex = useMemo(() => {
    // line index -> notes that match that line
    const matches = new Map<number, UiErrorNote[]>();

    const normalizedNotes = notes
      .map((note) => ({
        note,
        normalizedHighlightedText: normalizeForMatch(note.highlightedText),
      }))
      .filter(({ normalizedHighlightedText }) => normalizedHighlightedText.length > 0);

    parsedLogs.forEach((entry, index) => {
      const normalizedLine = normalizeForMatch(getLogEntryText(entry));

      const matchedNotes = normalizedNotes
        .filter(({ normalizedHighlightedText }) => normalizedLine.includes(normalizedHighlightedText))
        .map(({ note }) => note);

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

    const rect = range.getBoundingClientRect();
    setButtonPos({ x: rect.right + 6, y: rect.top - 4 });
    setSelectedText(text);
  }, []);

  const handleOpenModal = () => {
    setNoteText("");
    setIsModalOpen(true);
    // The floating button disappears once the modal opens
    setButtonPos(null);
  };

  const handleSubmitNote = () => {
    // TODO: replace this with a real API call to save the note to the backend
    // eslint-disable-next-line no-console
    // console.log("Saving error note:", { note: noteText, selectedText, currentUser, url: noteURL });
    // setIsModalOpen(false);
    // setSelectedText("");
    // setNoteText("");
    // setNoteURL("");
    // window.getSelection()?.removeAllRanges();
    const author = currentUser?.username?.trim();
    const trimmedNote = noteText.trim();
    const trimmedSelection = selectedText.trim();

    if (!author || !trimmedNote || !trimmedSelection) {
      toaster.create({
        description: "Missing note text, selected log text, or user information.",
        title: "Cannot save note",
        type: "error",
      });
      return;
    }

    saveNote({
      author,
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

  const pickBestMatchedNote = (matchedNotes: UiErrorNote[]): UiErrorNote | null => {
    if (matchedNotes.length === 0) {
      return null;
    }

    // Prefer the most specific signature (longest highlightedText).
    const sorted = [...matchedNotes].sort((a, b) => b.highlightedText.length - a.highlightedText.length);

    return sorted[0] ?? null;
  };

  const handleOpenMatchedNote = (lineIndex: number) => {
    const matchedNotes = matchingNotesByLineIndex.get(lineIndex) ?? [];
    const bestMatch = pickBestMatchedNote(matchedNotes);

    if (!bestMatch) {
      return;
    }

    setActiveMatchedLineIndex(lineIndex);
    setActiveMatchedNote(bestMatch);
    setIsKnowledgeModalOpen(true);
  };

  const handleCloseKnowledgeModal = () => {
    setIsKnowledgeModalOpen(false);
    setActiveMatchedLineIndex(null);
    setActiveMatchedNote(null);
  };

  return (
    <Box display="flex" flexDirection="column" flexGrow={1} h="100%" minHeight={0} position="relative">
      <ErrorAlert error={error ?? logError} />
      <ProgressBar size="xs" visibility={isLoading ? "visible" : "hidden"} />
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
                    <Tooltip content="View error note" openDelay={100}>
                      <IconButton
                        aria-label="View error note"
                        colorPalette="blue"
                        h="16px"
                        minW="16px"
                        onClick={() => handleOpenMatchedNote(virtualRow.index)}
                        px={0}
                        size="2xs"
                        title="View error note"
                        variant="ghost"
                        w="16px"
                      >
                        <FiBookOpen />
                      </IconButton>
                    </Tooltip>
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
                {activeMatchedNote?.highlightedText ?? "-"}
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
              <Text fontSize="sm" lineHeight="1.6" color="gray.800">
                {activeMatchedNote?.noteText ?? "-"}
              </Text>
            </Box>

            {/* Reference Documentation Section */}
            {activeMatchedNote?.externalUrl ? (
              <Box borderRadius="md" bg="blue.50" p={3} borderLeft="3px solid" borderColor="blue.400">
                <Text fontSize="xs" fontWeight="semibold" textTransform="uppercase" color="gray.600" mb={2}>
                  Reference Documentation
                </Text>
                <Text
                  as="a"
                  href={activeMatchedNote.externalUrl}
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
                  {activeMatchedNote.externalUrl}
                  <FiExternalLink size={14} />
                </Text>
              </Box>
            ) : null}
          </Dialog.Body>

          <Dialog.Footer pt={4} borderTop="1px solid" borderColor="gray.200">
            <HStack gap={2} justifyContent="flex-end">
              <Button onClick={handleCloseKnowledgeModal} variant="outline">
                Close
              </Button>
            </HStack>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Root>
    </Box>
  );
};