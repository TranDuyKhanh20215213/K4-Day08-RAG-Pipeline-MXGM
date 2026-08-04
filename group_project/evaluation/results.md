# RAG Evaluation Results

## Tổng quan

Bộ đánh giá gồm **15 câu hỏi tuyển sinh** thuộc hai nhóm nội dung chính: thông tin tuyển sinh của Đại học Dược Hà Nội và bảng ngành/chỉ tiêu/điểm chuẩn của Đại học Bách khoa - ĐHQG-HCM.

Hai cấu hình được so sánh:

- **Config A - Hybrid**: kết hợp tín hiệu lexical, BM25, exact match theo mã ngành/số liệu và ưu tiên ngữ cảnh dạng bảng.
- **Config B - Dense proxy**: sử dụng độ phủ token giữa câu hỏi và ngữ cảnh như một proxy cho dense retrieval trong môi trường đánh giá.

---

## Kết quả Heuristic

| Metric | Config A (Hybrid) | Config B (Dense proxy) | Delta |
|---|---:|---:|---:|
| Faithfulness | 0.808 | 0.795 | +0.013 |
| Answer Relevance | 0.810 | 0.694 | +0.117 |
| Context Recall | 0.924 | 0.845 | +0.079 |
| Context Precision | 0.880 | 0.893 | -0.013 |
| **Average** | **0.856** | **0.807** | **+0.049** |

Bảng heuristic cho thấy Config A có lợi thế ở hầu hết các chỉ số, đặc biệt là **Answer Relevance** và **Context Recall**. Điều này cho thấy Config A lấy được nhiều bằng chứng phù hợp hơn với câu hỏi và tạo điều kiện để câu trả lời bám sát đáp án kỳ vọng hơn.

Config B có **Context Precision** nhỉnh hơn nhẹ, nghĩa là các ngữ cảnh được lấy ra có xu hướng cô đọng hơn một chút. Tuy nhiên, precision cao hơn không bù được phần recall và relevance thấp hơn.

---

## Kết quả RAGAS thật

| Metric | Config A (Hybrid) | Config B (Dense proxy) | Delta |
|---|---:|---:|---:|
| Faithfulness | 0.767 | 0.700 | +0.067 |
| Answer Relevance | 0.801 | 0.751 | +0.050 |
| Context Recall | 1.000 | 1.000 | +0.000 |
| Context Precision | 0.964 | 0.949 | +0.014 |
| **Average** | **0.883** | **0.850** | **+0.033** |

Theo RAGAS thật, **Config A - Hybrid đạt điểm trung bình cao hơn**, với **0.883** so với **0.850** của Config B.

---

## Diễn giải các chỉ số

### Faithfulness

Config A đạt **0.767**, cao hơn Config B ở mức **0.700**. Điều này cho thấy câu trả lời của Config A bám vào ngữ cảnh được cung cấp tốt hơn. Nói cách khác, các khẳng định trong câu trả lời của Config A có khả năng được hỗ trợ bởi context cao hơn.

Mức điểm này là khá ổn cho bài toán hỏi đáp trên dữ liệu bảng, nhưng chưa tuyệt đối. Nguyên nhân là một số câu trả lời vẫn có thể diễn đạt lại, tổng hợp hoặc rút gọn thông tin, khiến judge không xác nhận toàn bộ claim là được hỗ trợ trực tiếp.

### Answer Relevance

Config A đạt **0.801**, Config B đạt **0.751**. Đây là mức tốt, cho thấy câu trả lời nhìn chung đúng trọng tâm câu hỏi.

Config A cao hơn vì các câu hỏi trong bộ đánh giá thường chứa mã ngành, chỉ tiêu, điểm chuẩn hoặc tên ngành cụ thể. Khi những tín hiệu này được nhận diện tốt, câu trả lời dễ tập trung vào đúng fact cần trả lời hơn. Config B vẫn trả lời khá ổn, nhưng có xu hướng kém hơn khi câu hỏi cần khớp chính xác mã ngành hoặc số liệu.

### Context Recall

Cả hai config đều đạt **1.000**. Điều này có nghĩa là ngữ cảnh được lấy ra đã chứa đủ thông tin cần thiết để trả lời các câu hỏi trong golden dataset.

Điểm recall bằng 1 không có nghĩa toàn bộ pipeline hoàn hảo. Nó chỉ nói rằng evidence cần thiết đã xuất hiện trong context. Việc mô hình có dùng đúng evidence đó để sinh câu trả lời hay không được phản ánh thêm qua Faithfulness và Answer Relevance.

### Context Precision

Config A đạt **0.964**, Config B đạt **0.949**. Cả hai đều rất cao, nghĩa là phần lớn context retrieved là hữu ích, ít nhiễu.

Config A nhỉnh hơn nhẹ vì khi câu hỏi có mã ngành hoặc số liệu cụ thể, context được chọn thường chứa đúng bảng hoặc dòng dữ liệu liên quan. Config B vẫn có precision cao, nhưng đôi khi lấy thêm context cùng chủ đề mà không trực tiếp chứa fact chính.

---

## Vì sao Config A tốt hơn

Config A tốt hơn chủ yếu vì bài toán này có nhiều dữ liệu dạng bảng: mã ngành, chỉ tiêu, tổ hợp xét tuyển và điểm chuẩn. Các thông tin này cần khớp chính xác, đặc biệt với các mã như `106`, `108`, `146`, `228`, `406` hoặc các số liệu như `240`, `670`, `85.41`.

Hybrid retrieval tận dụng được nhiều loại tín hiệu cùng lúc:

- Từ khóa trong câu hỏi
- Mã ngành và số liệu
- Tên ngành hoặc tên trường
- Cấu trúc bảng
- Độ phủ nội dung giữa câu hỏi và context

Nhờ đó, Config A lấy được context vừa đủ rộng để chứa evidence, vừa đủ chính xác để hỗ trợ câu trả lời.

---

## Vì sao Context Recall cao nhưng điểm khác chưa tuyệt đối

Context Recall cao cho thấy thông tin cần thiết đã có trong context. Tuy nhiên, câu trả lời cuối cùng còn phụ thuộc vào bước generation. Với dữ liệu bảng, mô hình có thể:

- Diễn đạt lại khác với expected answer
- Bỏ bớt một chi tiết phụ
- Trả lời thận trọng nếu context không được hiểu là đủ rõ
- Gắn citation chưa khớp hoàn toàn với từng claim

Vì vậy Faithfulness và Answer Relevance chưa đạt 0.9, dù Context Recall đã đạt 1.0.

---

## Các trường hợp còn yếu

| Câu hỏi | Điểm trung bình | Nguyên nhân chính |
|---|---:|---|
| Nhóm ngành mã 108 của HCMUT có bao nhiêu chỉ tiêu? | 0.704 | Context có bằng chứng đúng nhưng còn lẫn thêm các dòng bảng gần giống, làm precision thấp hơn. |
| Ở chương trình tiêu chuẩn HCMUT, mã ngành 106 tương ứng ngành nào? | 0.757 | Câu hỏi rất ngắn, phụ thuộc mạnh vào việc khớp đúng mã ngành; chỉ cần context có thêm ngành gần kề là judge sẽ chấm khắt khe hơn. |
| Chương trình liên kết Cử nhân Kỹ thuật Quốc tế của HCMUT có ngành Trí tuệ Nhân tạo mã 406 với điểm chuẩn 2025 bao nhiêu? | 0.789 | Câu hỏi chứa nhiều thực thể trong cùng một câu, nên answer cần vừa nhận diện đúng chương trình, vừa đúng ngành, mã ngành và điểm chuẩn. |

Nhìn chung, các trường hợp yếu đều liên quan đến dữ liệu bảng có nhiều dòng tương tự nhau. Khi nhiều ngành nằm gần nhau trong cùng một ngữ cảnh, mô hình vẫn có thể trả lời đúng nhưng điểm precision hoặc faithfulness bị giảm do phần context dư.

---

## Kết luận

Kết quả hiện tại được xem là **ổn và đủ tốt cho bài đánh giá RAG pipeline**:

- Config A đạt average **0.883**, vượt ngưỡng tốt 0.8.
- Config B đạt average **0.850**, cũng ở mức tốt nhưng thấp hơn Config A.
- Cả hai đều retrieve đủ evidence, thể hiện qua Context Recall **1.000**.
- Config A phù hợp hơn với dữ liệu tuyển sinh dạng bảng vì khai thác tốt exact match và tín hiệu lexical.

Kết luận cuối cùng: **Config A - Hybrid là cấu hình tốt hơn trong bộ đánh giá này**.
