-- ============================================================
-- FULL TOPICS SEED DATA
-- Run after db.sql is loaded
-- ============================================================

-- Hàm tạo random vector 1536 chiều (placeholder, replace với actual embeddings khi cần)
-- Để null hoặc dùng: array[rand(), rand(), ...]::vector

-- ============================================================
-- 1. Ngôn ngữ (26c225aa-1023-4221-b09e-0354756c394c)
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), '26c225aa-1023-4221-b09e-0354756c394c', 'Tiếng Anh', 'tieng-anh', 'Chủ đề học Tiếng Anh từ cơ bản đến nâng cao, bao gồm ngữ pháp, từ vựng, kỹ năng nghe, nói, đọc, viết cho giao tiếp và công việc.', 1, true, now(), now()),
  (gen_random_uuid(), '26c225aa-1023-4221-b09e-0354756c394c', 'Tiếng Trung', 'tieng-trung', 'Học Tiếng Trung Quốc (Hán ngữ) với pinyin, chữ Hán, ngữ pháp và giao tiếp hàng ngày.', 2, true, now(), now()),
  (gen_random_uuid(), '26c225aa-1023-4221-b09e-0354756c394c', 'Tiếng Nhật', 'tieng-nhat', 'Học Tiếng Nhật từ Hiragana, Katakana, Kanji đến giao tiếp N3-N1, phục vụ du học và làm việc.', 3, true, now(), now()),
  (gen_random_uuid(), '26c225aa-1023-4221-b09e-0354756c394c', 'Tiếng Hàn', 'tieng-han', 'Học Tiếng Hàn Quốc từ bảng chữ cái Hangul đến giao tiếp TOPIK, văn hóa và K-pop.', 4, true, now(), now()),
  (gen_random_uuid(), '26c225aa-1023-4221-b09e-0354756c394c', 'Tiếng Pháp', 'tieng-phap', 'Học Tiếng Pháp cho người mới bắt đầu, giao tiếp, du lịch và công việc quốc tế.', 5, true, now(), now()),
  (gen_random_uuid(), '26c225aa-1023-4221-b09e-0354756c394c', 'Tiếng Đức', 'tieng-duc', 'Học Tiếng Đức A1-C2, ngữ pháp, từ vựng chuyên ngành cho du học và định cư.', 6, true, now(), now()),
  (gen_random_uuid(), '26c225aa-1023-4221-b09e-0354756c394c', 'Tiếng Tây Ban Nha', 'tieng-tay-ban-nha', 'Học Tiếng Tây Ban Nha (Español) cho giao tiếp, du lịch và công việc.', 7, true, now(), now()),
  (gen_random_uuid(), '26c225aa-1023-4221-b09e-0354756c394c', 'Tiếng Bồ Đào Nha', 'tieng-bo-dao-nha', 'Học Tiếng Bồ Đào Nha (Português) cho giao tiếp Brasil và Bồ Đào Nha.', 8, true, now(), now()),
  (gen_random_uuid(), '26c225aa-1023-4221-b09e-0354756c394c', 'Dịch thuật', 'dich-thuat', 'Kỹ năng dịch thuật, biên phiên dịch, công cụ dịch và quản lý dự án dịch thuật.', 9, true, now(), now()),
  (gen_random_uuid(), '26c225aa-1023-4221-b09e-0354756c394c', 'Ngữ pháp & Từ vựng', 'ngu-phap-tu-vung', 'Luyện ngữ pháp và từ vựng chuyên sâu cho các ngôn ngữ, phục vụ thi cử và giao tiếp.', 10, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 2. Phát triển (1eae48c2-90db-4f45-a224-79b860bf70d7)
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), '1eae48c2-90db-4f45-a224-79b860bf70d7', 'Kỹ năng mềm', 'ky-nang-mem', 'Phát triển kỹ năng giao tiếp, làm việc nhóm, quản lý thời gian, giải quyết vấn đề và tư duy sáng tạo.', 1, true, now(), now()),
  (gen_random_uuid(), '1eae48c2-90db-4f45-a224-79b860bf70d7', 'Kỹ năng lãnh đạo', 'ky-nang-lanh-dao', 'Học cách lãnh đạo, quản lý đội nhóm, ra quyết định và truyền cảm hứng.', 2, true, now(), now()),
  (gen_random_uuid(), '1eae48c2-90db-4f45-a224-79b860bf70d7', 'Tư duy phản biện', 'tu-duy-phan-bien', 'Rèn luyện tư duy phản biện, phân tích logic, đánh giá thông tin và đưa ra kết luận đúng đắn.', 3, true, now(), now()),
  (gen_random_uuid(), '1eae48c2-90db-4f45-a224-79b860bf70d7', 'Quản lý dự án', 'quan-ly-du-an', 'Học quản lý dự án từ khởi đầu đến hoàn thành, sử dụng các phương pháp như Agile, Scrum, Kanban.', 4, true, now(), now()),
  (gen_random_uuid(), '1eae48c2-90db-4f45-a224-79b860bf70d7', 'Thuyết trình', 'thuyet-trinh', 'Kỹ năng thuyết trình hiệu quả, thiết kế slide, xử lý tình huống và thu hút khán giả.', 5, true, now(), now()),
  (gen_random_uuid(), '1eae48c2-90db-4f45-a224-79b860bf70d7', 'Networking', 'networking', 'Xây dựng mối quan hệ chuyên nghiệp, mở rộng mạng lưới contacts và cơ hội nghề nghiệp.', 6, true, now(), now()),
  (gen_random_uuid(), '1eae48c2-90db-4f45-a224-79b860bf70d7', 'Quản lý cảm xúc', 'quan-ly-cam-xuc', 'Kỹ năng quản lý stress, kiểm soát cảm xúc và duy trì sức khỏe tinh thần trong công việc.', 7, true, now(), now()),
  (gen_random_uuid(), '1eae48c2-90db-4f45-a224-79b860bf70d7', 'Thương lượng', 'thuong-luong', 'Kỹ năng đàm phán, thương lượng lương, deal và xử lý xung đột trong kinh doanh.', 8, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 3. Kinh doanh (7777cb92-e3fa-4914-9b70-f25a6bdc783b)
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), '7777cb92-e3fa-4914-9b70-f25a6bdc783b', 'Khởi nghiệp', 'khoi-nghiep', 'Học cách bắt đầu startup, ý tưởng kinh doanh, business plan, gây vốn và xây dựng đội nhóm.', 1, true, now(), now()),
  (gen_random_uuid(), '7777cb92-e3fa-4914-9b70-f25a6bdc783b', 'Marketing', 'marketing', 'Chiến lược marketing, digital marketing, content marketing, SEO, quảng cáo và branding.', 2, true, now(), now()),
  (gen_random_uuid(), '7777cb92-e3fa-4914-9b70-f25a6bdc783b', 'Bán hàng', 'ban-hang', 'Kỹ năng bán hàng, chốt deal, chăm sóc khách hàng, CRM và mở rộng kênh phân phối.', 3, true, now(), now()),
  (gen_random_uuid(), '7777cb92-e3fa-4914-9b70-f25a6bdc783b', 'Quản trị kinh doanh', 'quan-tri-kinh-doanh', 'Quản lý doanh nghiệp, chiến lược kinh doanh, SWOT analysis và cạnh tranh thị trường.', 4, true, now(), now()),
  (gen_random_uuid(), '7777cb92-e3fa-4914-9b70-f25a6bdc783b', 'E-commerce', 'e-commerce', 'Xây dựng và vận hành cửa hàng online, Shopify, sàn thương mại điện tử và fulfillment.', 5, true, now(), now()),
  (gen_random_uuid(), '7777cb92-e3fa-4914-9b70-f25a6bdc783b', 'Franchise', 'franchise', 'Mô hình nhượng quyền thương mại, đánh giá cơ hội franchise và quản lý chuỗi.', 6, true, now(), now()),
  (gen_random_uuid(), '7777cb92-e3fa-4914-9b70-f25a6bdc783b', 'Chuỗi cung ứng', 'chuoi-cung-ung', 'Quản lý chuỗi cung ứng, logistics, kho vận và tối ưu hóa vận chuyển.', 7, true, now(), now()),
  (gen_random_uuid(), '7777cb92-e3fa-4914-9b70-f25a6bdc783b', 'Đầu tư', 'dau-tu', 'Kiến thức đầu tư chứng khoán, bất động sản, quỹ, startup và quản lý danh mục đầu tư.', 8, true, now(), now()),
  (gen_random_uuid(), '7777cb92-e3fa-4914-9b70-f25a6bdc783b', 'Import - Export', 'import-export', 'Kinh doanh xuất nhập khẩu, Incoterms, thủ tục hải quan và logistics quốc tế.', 9, true, now(), now()),
  (gen_random_uuid(), '7777cb92-e3fa-4914-9b70-f25a6bdc783b', 'Thương mại quốc tế', 'thuong-mai-quoc-te', 'Chiến lược kinh doanh quốc tế, đàm phán xuyên biên giới và mở rộng thị trường toàn cầu.', 10, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 4. Tài chính và kế toán (9e20d328-81d2-4829-8082-77db21bcd5d3)
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), '9e20d328-81d2-4829-8082-77db21bcd5d3', 'Kế toán tổng hợp', 'ke-toan-tong-hop', 'Học kế toán tổng hợp, lập báo cáo tài chính, bảng cân đối kế toán và báo cáo kết quả kinh doanh.', 1, true, now(), now()),
  (gen_random_uuid(), '9e20d328-81d2-4829-8082-77db21bcd5d3', 'Kế toán thuế', 'ke-toan-thue', 'Xử lý thuế thu nhập doanh nghiệp, VAT, cá nhân và tuân thủ quy định thuế hiện hành.', 2, true, now(), now()),
  (gen_random_uuid(), '9e20d328-81d2-4829-8082-77db21bcd5d3', 'Tài chính doanh nghiệp', 'tai-chinh-doanh-nghiep', 'Phân tích báo cáo tài chính, quản lý dòng tiền, định giá doanh nghiệp và quyết định đầu tư.', 3, true, now(), now()),
  (gen_random_uuid(), '9e20d328-81d2-4829-8082-77db21bcd5d3', 'Chứng khoán', 'chung-khoan', 'Phân tích kỹ thuật, phân tích cơ bản, trading strategies và đầu tư chứng khoán.', 4, true, now(), now()),
  (gen_random_uuid(), '9e20d328-81d2-4829-8082-77db21bcd5d3', 'Ngân hàng', 'ngan-hang', 'Hoạt động ngân hàng, tín dụng, thanh toán quốc tế, Basel III và quản lý rủi ro tín dụng.', 5, true, now(), now()),
  (gen_random_uuid(), '9e20d328-81d2-4829-8082-77db21bcd5d3', 'Bảo hiểm', 'bao-hiem', 'Nghiệp vụ bảo hiểm nhân thọ, bảo hiểm phi nhân thọ, định giá rủi ro và bồi thường.', 6, true, now(), now()),
  (gen_random_uuid(), '9e20d328-81d2-4829-8082-77db21bcd5d3', 'Tài chính cá nhân', 'tai-chinh-ca-nhan', 'Quản lý tài chính cá nhân, tiết kiệm, đầu tư, mua bảo hiểm và lập kế hoạch nghỉ hưu.', 7, true, now(), now()),
  (gen_random_uuid(), '9e20d328-81d2-4829-8082-77db21bcd5d3', 'Kiểm toán', 'kiem-toan', 'Kiểm toán nội bộ, kiểm toán độc lập, SOX compliance và quy trình kiểm toán chuẩn.', 8, true, now(), now()),
  (gen_random_uuid(), '9e20d328-81d2-4829-8082-77db21bcd5d3', 'Phân tích tài chính', 'phan-tich-tai-chinh', 'Financial modeling, valuation, DCF analysis và các công cụ phân tích tài chính nâng cao.', 9, true, now(), now()),
  (gen_random_uuid(), '9e20d328-81d2-4829-8082-77db21bcd5d3', 'Excel cho tài chính', 'excel-cho-tai-chinh', 'Sử dụng Excel cho kế toán, tài chính: Pivot Table, VLOOKUP, financial modeling và automation.', 10, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 5. CNTT và Phần mềm (3fbaeb24-813f-49cd-9e06-cf7d58b8d2bc) - đã có 3 topics
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), '3fbaeb24-813f-49cd-9e06-cf7d58b8d2bc', 'An toàn thông tin', 'an-toan-thong-tin', 'Bảo mật thông tin, ethical hacking, penetration testing, mã hóa và phòng chống tấn công mạng.', 4, true, now(), now()),
  (gen_random_uuid(), '3fbaeb24-813f-49cd-9e06-cf7d58b8d2bc', 'Cloud Computing', 'cloud-computing', 'AWS, Azure, Google Cloud, kiến trúc cloud, serverless và DevOps.', 5, true, now(), now()),
  (gen_random_uuid(), '3fbaeb24-813f-49cd-9e06-cf7d58b8d2bc', 'Database', 'database', 'Thiết kế database, SQL, NoSQL, PostgreSQL, MongoDB, tối ưu hóa truy vấn và data modeling.', 6, true, now(), now()),
  (gen_random_uuid(), '3fbaeb24-813f-49cd-9e06-cf7d58b8d2bc', 'DevOps', 'devops', 'CI/CD, Docker, Kubernetes, Jenkins, GitHub Actions và tự động hóa deployment.', 7, true, now(), now()),
  (gen_random_uuid(), '3fbaeb24-813f-49cd-9e06-cf7d58b8d2bc', 'AI & Machine Learning', 'ai-machine-learning', 'Trí tuệ nhân tạo, machine learning, deep learning, NLP và ứng dụng AI trong thực tế.', 8, true, now(), now()),
  (gen_random_uuid(), '3fbaeb24-813f-49cd-9e06-cf7d58b8d2bc', 'Data Science', 'data-science', 'Phân tích dữ liệu, Python, Pandas, NumPy, visualization và machine learning cơ bản.', 9, true, now(), now()),
  (gen_random_uuid(), '3fbaeb24-813f-49cd-9e06-cf7d58b8d2bc', 'Mạng máy tính', 'mang-may-tinh', 'CCNA, network protocols, OSI model, routing, switching và quản trị hệ thống mạng.', 10, true, now(), now()),
  (gen_random_uuid(), '3fbaeb24-813f-49cd-9e06-cf7d58b8d2bc', 'Hệ điều hành', 'he-dieu-hanh', 'Linux, Windows Server, quản trị hệ thống, shell scripting và automation.', 11, true, now(), now()),
  (gen_random_uuid(), '3fbaeb24-813f-49cd-9e06-cf7d58b8d2bc', 'Blockchain', 'blockchain', 'Công nghệ blockchain, smart contract, Ethereum, NFT và ứng dụng phi tập trung (DeFi).', 12, true, now(), now()),
  (gen_random_uuid(), '3fbaeb24-813f-49cd-9e06-cf7d58b8d2bc', 'IoT', 'iot', 'Internet of Things, Arduino, Raspberry Pi, cảm biến và xây dựng hệ thống IoT.', 13, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 6. Năng suất văn phòng (a1bac64a-616d-4639-83bc-98855c691deb)
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), 'a1bac64a-616d-4639-83bc-98855c691deb', 'Microsoft Word', 'microsoft-word', 'Soạn thảo văn bản chuyên nghiệp với Word: định dạng, styles, table of contents, mail merge.', 1, true, now(), now()),
  (gen_random_uuid(), 'a1bac64a-616d-4639-83bc-98855c691deb', 'Microsoft Excel', 'microsoft-excel', 'Excel nâng cao: Pivot Table, VLOOKUP, SUMIFS, macros, VBA và automation.', 2, true, now(), now()),
  (gen_random_uuid(), 'a1bac64a-616d-4639-83bc-98855c691deb', 'Microsoft PowerPoint', 'microsoft-powerpoint', 'Thiết kế slide đẹp, animation, presenter view và kỹ thuật thuyết trình chuyên nghiệp.', 3, true, now(), now()),
  (gen_random_uuid(), 'a1bac64a-616d-4639-83bc-98855c691deb', 'Google Workspace', 'google-workspace', 'Google Docs, Sheets, Slides, Forms, Drive và cộng tác nhóm hiệu quả.', 4, true, now(), now()),
  (gen_random_uuid(), 'a1bac64a-616d-4639-83bc-98855c691deb', 'Notion', 'notion', 'Sử dụng Notion để quản lý dự án, wiki, CRM và workspace cá nhân.', 5, true, now(), now()),
  (gen_random_uuid(), 'a1bac64a-616d-4639-83bc-98855c691deb', 'Quản lý thời gian', 'quan-ly-thoi-gian', 'Kỹ thuật quản lý thời gian: Pomodoro, Eisenhower matrix, OKR và Productivity systems.', 6, true, now(), now()),
  (gen_random_uuid(), 'a1bac64a-616d-4639-83bc-98855c691deb', 'Giao tiếp văn phòng', 'giao-tiep-van-phong', 'Kỹ năng email, họp hiệu quả, viết business writing và giao tiếp chuyên nghiệp.', 7, true, now(), now()),
  (gen_random_uuid(), 'a1bac64a-616d-4639-83bc-98855c691deb', 'PDF & Scan', 'pdf-scan', 'Tạo, chỉnh sửa PDF, OCR, combine files và quản lý tài liệu số.', 8, true, now(), now()),
  (gen_random_uuid(), 'a1bac64a-616d-4639-83bc-98855c691deb', 'Zoom & Meeting', 'zoom-meeting', 'Tổ chức họp trực tuyến hiệu quả, Zoom, Teams, Google Meet và remote collaboration.', 9, true, now(), now()),
  (gen_random_uuid(), 'a1bac64a-616d-4639-83bc-98855c691deb', 'Công cụ AI văn phòng', 'cong-cu-ai-van-phong', 'Ứng dụng AI vào công việc văn phòng: ChatGPT, Copilot, automation và productivity tools.', 10, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 7. Phát triển cá nhân (b0ba86b3-3022-4f71-ad66-30bffb825ded)
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), 'b0ba86b3-3022-4f71-ad66-30bffb825ded', 'Thiền định & Mindfulness', 'thien-dinh-mindfulness', 'Rèn luyện tập trung, giảm stress qua thiền định, breathing exercises và mindfulness.', 1, true, now(), now()),
  (gen_random_uuid(), 'b0ba86b3-3022-4f71-ad66-30bffb825ded', 'Đọc sách hiệu quả', 'doc-sach-hieu-qua', 'Kỹ thuật đọc nhanh, đọc chọn lọc, note-taking và áp dụng kiến thức từ sách.', 2, true, now(), now()),
  (gen_random_uuid(), 'b0ba86b3-3022-4f71-ad66-30bffb825ded', 'Tự học', 'tu-hoc', 'Phương pháp tự học hiệu quả, learning strategies, spaced repetition và building habits.', 3, true, now(), now()),
  (gen_random_uuid(), 'b0ba86b3-3022-4f71-ad66-30bffb825ded', 'Xây dựng thương hiệu cá nhân', 'xay-dung-thuong-hieu-ca-nhan', 'Personal branding, LinkedIn optimization, viết blog và xây dựng uy tín chuyên gia.', 4, true, now(), now()),
  (gen_random_uuid(), 'b0ba86b3-3022-4f71-ad66-30bffb825ded', 'Sức khỏe & Wellness', 'suc-khoe-wellness', 'Dinh dưỡng, tập thể dục, giấc ngủ chất lượng và cân bằng cuộc sống công việc.', 5, true, now(), now()),
  (gen_random_uuid(), 'b0ba86b3-3022-4f71-ad66-30bffb825ded', 'Tài chính cá nhân', 'tai-chinh-ca-nhan-ptcn', 'Quản lý tiền bạc, tiết kiệm, đầu tư và lập kế hoạch tài chính dài hạn.', 6, true, now(), now()),
  (gen_random_uuid(), 'b0ba86b3-3022-4f71-ad66-30bffb825ded', 'Kỹ năng sống', 'ky-nang-song', 'Các kỹ năng thiết yếu: nấu ăn, tài chính, sửa chữa nhỏ và independent living.', 7, true, now(), now()),
  (gen_random_uuid(), 'b0ba86b3-3022-4f71-ad66-30bffb825ded', 'Lập kế hoạch', 'lap-ke-hoach', 'Goal setting, OKR, habit tracking và chiến lược đạt được mục tiêu ngắn và dài hạn.', 8, true, now(), now()),
  (gen_random_uuid(), 'b0ba86b3-3022-4f71-ad66-30bffb825ded', 'Giao tiếp xã hội', 'giao-tiep-xa-hoi', 'Kỹ năng giao tiếp, xây dựng quan hệ, xử lý tình huống và mở rộng mạng lưới.', 9, true, now(), now()),
  (gen_random_uuid(), 'b0ba86b3-3022-4f71-ad66-30bffb825ded', 'Sáng tạo & Design Thinking', 'sang-tao-design-thinking', 'Rèn luyện tư duy sáng tạo, design thinking, brainstorming và giải quyết vấn đề sáng tạo.', 10, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 8. Thiết kế (5559a214-7ee4-47e4-b8b4-baad277bae7f)
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), '5559a214-7ee4-47e4-b8b4-baad277bae7f', 'UI Design', 'ui-design', 'Thiết kế giao diện người dùng: color theory, typography, layout, Figma và design systems.', 1, true, now(), now()),
  (gen_random_uuid(), '5559a214-7ee4-47e4-b8b4-baad277bae7f', 'UX Design', 'ux-design', 'Trải nghiệm người dùng: user research, wireframing, prototyping, usability testing.', 2, true, now(), now()),
  (gen_random_uuid(), '5559a214-7ee4-47e4-b8b4-baad277bae7f', 'Graphic Design', 'graphic-design', 'Thiết kế đồ họa: Adobe Photoshop, Illustrator, poster, banner, branding và visual identity.', 3, true, now(), now()),
  (gen_random_uuid(), '5559a214-7ee4-47e4-b8b4-baad277bae7f', 'Motion Graphics', 'motion-graphics', 'Animation, video editing, After Effects, kinetic typography và motion design.', 4, true, now(), now()),
  (gen_random_uuid(), '5559a214-7ee4-47e4-b8b4-baad277bae7f', '3D Design', '3d-design', 'Blender, Cinema 4D, model 3D, rendering và tạo hình ảnh ba chiều.', 5, true, now(), now()),
  (gen_random_uuid(), '5559a214-7ee4-47e4-b8b4-baad277bae7f', 'Illustration', 'illustration', 'Vẽ minh họa kỹ thuật số, digital painting, character design và artwork.', 6, true, now(), now()),
  (gen_random_uuid(), '5559a214-7ee4-47e4-b8b4-baad277bae7f', 'Photography', 'photography', 'Nhiếp ảnh, composition, editing (Lightroom), portrait và landscape photography.', 7, true, now(), now()),
  (gen_random_uuid(), '5559a214-7ee4-47e4-b8b4-baad277bae7f', 'Typography', 'typography', 'Thiết kế chữ, font pairing, hierarchy và typographic systems.', 8, true, now(), now()),
  (gen_random_uuid(), '5559a214-7ee4-47e4-b8b4-baad277bae7f', 'Branding', 'branding', 'Xây dựng thương hiệu, logo design, brand guidelines và visual identity system.', 9, true, now(), now()),
  (gen_random_uuid(), '5559a214-7ee4-47e4-b8b4-baad277bae7f', 'Web Design', 'web-design', 'Thiết kế website: layout, responsive, UX/UI web, Figma và design handoff.', 10, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 9. Marketing (Maketting) (27378b01-bff7-448b-8603-0f4e7e88bd76)
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), '27378b01-bff7-448b-8603-0f4e7e88bd76', 'Digital Marketing', 'digital-marketing', 'Marketing online toàn diện: SEO, SEM, social media, email marketing và digital strategy.', 1, true, now(), now()),
  (gen_random_uuid(), '27378b01-bff7-448b-8603-0f4e7e88bd76', 'Content Marketing', 'content-marketing', 'Chiến lược content, copywriting, blog, video content và content calendar.', 2, true, now(), now()),
  (gen_random_uuid(), '27378b01-bff7-448b-8603-0f4e7e88bd76', 'SEO', 'seo', 'Search Engine Optimization: on-page, off-page, technical SEO, link building và keyword research.', 3, true, now(), now()),
  (gen_random_uuid(), '27378b01-bff7-448b-8603-0f4e7e88bd76', 'Social Media Marketing', 'social-media-marketing', 'Marketing trên Facebook, Instagram, TikTok, LinkedIn và quản lý cộng đồng.', 4, true, now(), now()),
  (gen_random_uuid(), '27378b01-bff7-448b-8603-0f4e7e88bd76', 'Google Ads', 'google-ads', 'Quảng cáo Google: Search, Display, Shopping, YouTube ads và optimization.', 5, true, now(), now()),
  (gen_random_uuid(), '27378b01-bff7-448b-8603-0f4e7e88bd76', 'Facebook & Instagram Ads', 'facebook-instagram-ads', 'Chạy quảng cáo Facebook Ads Manager, targeting, retargeting và conversion optimization.', 6, true, now(), now()),
  (gen_random_uuid(), '27378b01-bff7-448b-8603-0f4e7e88bd76', 'Email Marketing', 'email-marketing', 'Xây dựng list, email automation, nurture sequence và đo lường email campaign.', 7, true, now(), now()),
  (gen_random_uuid(), '27378b01-bff7-448b-8603-0f4e7e88bd76', 'Analytics', 'analytics', 'Google Analytics 4, data-driven marketing, KPI tracking và reporting.', 8, true, now(), now()),
  (gen_random_uuid(), '27378b01-bff7-448b-8603-0f4e7e88bd76', 'Influencer Marketing', 'influencer-marketing', 'Hợp tác với influencer, KOL, đo lường ROI và xây dựng chiến dịch influencer.', 9, true, now(), now()),
  (gen_random_uuid(), '27378b01-bff7-448b-8603-0f4e7e88bd76', 'TikTok Marketing', 'tiktok-marketing', 'Marketing trên TikTok, viral content, TikTok Ads và thuật toán platform.', 10, true, now(), now()),
  (gen_random_uuid(), '27378b01-bff7-448b-8603-0f4e7e88bd76', 'Marketing Automation', 'marketing-automation', 'Automation với HubSpot, Mailchimp, Zapier và workflow marketing.', 11, true, now(), now()),
  (gen_random_uuid(), '27378b01-bff7-448b-8603-0f4e7e88bd76', 'PR & Truyền thông', 'pr-truyen-thong', ' Quan hệ công chúng, media relations, crisis management và press release.', 12, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 10. Sức khỏe (a19d53cb-c82d-4226-b93d-126d64557299)
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), 'a19d53cb-c82d-4226-b93d-126d64557299', 'Dinh dưỡng', 'dinh-duong', 'Khoa học dinh dưỡng, chế độ ăn lành mạnh, meal planning và supplement.', 1, true, now(), now()),
  (gen_random_uuid(), 'a19d53cb-c82d-4226-b93d-126d64557299', 'Tập gym & Fitness', 'tap-gym-fitness', 'Bài tập gym, cardio, HIIT, strength training và xây dựng physique.', 2, true, now(), now()),
  (gen_random_uuid(), 'a19d53cb-c82d-4226-b93d-126d64557299', 'Yoga', 'yoga', 'Các tư thế yoga, pranayama, meditation và lợi ích sức khỏe của yoga.', 3, true, now(), now()),
  (gen_random_uuid(), 'a19d53cb-c82d-4226-b93d-126d64557299', 'Chạy bộ & Cardio', 'chay-bo-cardio', 'Chạy bộ, bơi lội, đạp xe và các bài tập cardio for endurance và sức khỏe tim mạch.', 4, true, now(), now()),
  (gen_random_uuid(), 'a19d53cb-c82d-4226-b93d-126d64557299', 'Sức khỏe tinh thần', 'suc-khoe-tinh-than', 'Mental health, trầm cảm, lo âu, tự kỷ và các rối loạn tâm lý phổ biến.', 5, true, now(), now()),
  (gen_random_uuid(), 'a19d53cb-c82d-4226-b93d-126d64557299', 'Ngủ & Nghỉ ngơi', 'ngu-nghi-ngoi', 'Sleep hygiene, chất lượng giấc ngủ, circadian rhythm và recovery.', 6, true, now(), now()),
  (gen_random_uuid(), 'a19d53cb-c82d-4226-b93d-126d64557299', 'Giới tính & Sức khỏe sinh sản', 'gioi-tinh-suc-khoe-sinh-san', 'Kiến thức sức khỏe sinh sản, contraceptive, STIs và healthy relationships.', 7, true, now(), now()),
  (gen_random_uuid(), 'a19d53cb-c82d-4226-b93d-126d64557299', 'Thiền định', 'thien-dinh-sk', 'Meditation, mindfulness practice, stress reduction và mental clarity.', 8, true, now(), now()),
  (gen_random_uuid(), 'a19d53cb-c82d-4226-b93d-126d64557299', 'Sức khỏe da', 'suc-khoe-da', 'Chăm sóc da, skincare routine, treatment và prevention of skin conditions.', 9, true, now(), now()),
  (gen_random_uuid(), 'a19d53cb-c82d-4226-b93d-126d64557299', 'First Aid & Cấp cứu', 'first-aid-cap-cuu', 'Sơ cấp cứu, CPR, xử lý khẩn cấp và basic life support.', 10, true, now(), now()),
  (gen_random_uuid(), 'a19d53cb-c82d-4226-b93d-126d64557299', 'Pilates', 'pilates', 'Pilates matwork, reformer pilates, core strength và flexibility.', 11, true, now(), now()),
  (gen_random_uuid(), 'a19d53cb-c82d-4226-b93d-126d64557299', 'Gym tại nhà', 'gym-tai-nha', 'Home workout, calisthenics, resistance bands và bodyweight exercises.', 12, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 11. Âm nhạc (9e083f0a-9cc1-4174-bd5c-528508c309fa)
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), '9e083f0a-9cc1-4174-bd5c-528508c309fa', 'Guitar', 'guitar', 'Học guitar điện, guitar acoustic, fingerstyle, plectrum và các kỹ thuật chơi guitar.', 1, true, now(), now()),
  (gen_random_uuid(), '9e083f0a-9cc1-4174-bd5c-528508c309fa', 'Piano', 'piano', 'Chơi piano cổ điển và đại chúng, reading music, harmony và piano techniques.', 2, true, now(), now()),
  (gen_random_uuid(), '9e083f0a-9cc1-4174-bd5c-528508c309fa', 'Trống', 'trong', 'Drum set, percussion, rhythm, timing và các phong cách chơi trống khác nhau.', 3, true, now(), now()),
  (gen_random_uuid(), '9e083f0a-9cc1-4174-bd5c-528508c309fa', 'Hát', 'hat', 'Vocal training, kỹ thuật hát, breathing, pitch control và phát triển giọng hát.', 4, true, now(), now()),
  (gen_random_uuid(), '9e083f0a-9cc1-4174-bd5c-528508c309fa', 'Production nhạc', 'production-nhac', 'Music production với FL Studio, Ableton, Logic Pro, mixing và mastering.', 5, true, now(), now()),
  (gen_random_uuid(), '9e083f0a-9cc1-4174-bd5c-528508c309fa', 'Keyboard & Synth', 'keyboard-synth', 'Chơi keyboard, synthesizer, electronic music và sound design.', 6, true, now(), now()),
  (gen_random_uuid(), '9e083f0a-9cc1-4174-bd5c-528508c309fa', 'Nhạc lý', 'nhac-ly', 'Lý thuyết âm nhạc, scale, chord, harmony, ear training và sight-reading.', 7, true, now(), now()),
  (gen_random_uuid(), '9e083f0a-9cc1-4174-bd5c-528508c309fa', 'Violin', 'violin', 'Chơi violin cổ điển, technique, bow control và repertoire violin.', 8, true, now(), now()),
  (gen_random_uuid(), '9e083f0a-9cc1-4174-bd5c-528508c309fa', 'Saxophone', 'saxophone', 'Chơi saxophone jazz, classical, improvisation và technique.', 9, true, now(), now()),
  (gen_random_uuid(), '9e083f0a-9cc1-4174-bd5c-528508c309fa', 'DJ', 'dj', 'DJ skills, mixing, beatmatching, turntablism và setup DJ equipment.', 10, true, now(), now()),
  (gen_random_uuid(), '9e083f0a-9cc1-4174-bd5c-528508c309fa', 'Beatbox', 'beatbox', 'Kỹ thuật beatbox, vocal percussion và tạo nhịp bằng miệng.', 11, true, now(), now()),
  (gen_random_uuid(), '9e083f0a-9cc1-4174-bd5c-528508c309fa', 'Ukulele', 'ukulele', 'Chơi ukulele, chord, strumming patterns và popular songs.', 12, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 12. Phát triển Web (ec6dc1bb-5376-49ee-b23a-040b45672656) - sub của Phát triển
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), 'ec6dc1bb-5376-49ee-b23a-040b45672656', 'HTML & CSS', 'html-css', 'Nền tảng web: HTML5, CSS3, Flexbox, Grid, responsive design và CSS animations.', 1, true, now(), now()),
  (gen_random_uuid(), 'ec6dc1bb-5376-49ee-b23a-040b45672656', 'JavaScript', 'javascript', 'JavaScript ES6+, DOM manipulation, async/await, modules và modern JS features.', 2, true, now(), now()),
  (gen_random_uuid(), 'ec6dc1bb-5376-49ee-b23a-040b45672656', 'React', 'react', 'React hooks, state management, Next.js, Server Components và React ecosystem.', 3, true, now(), now()),
  (gen_random_uuid(), 'ec6dc1bb-5376-49ee-b23a-040b45672656', 'Vue.js', 'vue-js', 'Vue 3, Composition API, Pinia, Nuxt.js và Vue ecosystem.', 4, true, now(), now()),
  (gen_random_uuid(), 'ec6dc1bb-5376-49ee-b23a-040b45672656', 'Angular', 'angular', 'Angular framework, TypeScript, RxJS, Angular Material và enterprise patterns.', 5, true, now(), now()),
  (gen_random_uuid(), 'ec6dc1bb-5376-49ee-b23a-040b45672656', 'Node.js', 'node-js', 'Backend với Node.js, Express, REST APIs, authentication và middleware.', 6, true, now(), now()),
  (gen_random_uuid(), 'ec6dc1bb-5376-49ee-b23a-040b45672656', 'Python Web', 'python-web', 'Django, Flask, FastAPI và xây dựng web applications với Python.', 7, true, now(), now()),
  (gen_random_uuid(), 'ec6dc1bb-5376-49ee-b23a-040b45672656', 'PHP & Laravel', 'php-laravel', 'PHP 8, Laravel framework, Eloquent, Blade templates và Laravel ecosystem.', 8, true, now(), now()),
  (gen_random_uuid(), 'ec6dc1bb-5376-49ee-b23a-040b45672656', 'WordPress', 'wordpress', 'WordPress development, themes, plugins, Gutenberg và custom post types.', 9, true, now(), now()),
  (gen_random_uuid(), 'ec6dc1bb-5376-49ee-b23a-040b45672656', 'TypeScript', 'typescript', 'TypeScript type system, generics, decorators, OOP và functional patterns.', 10, true, now(), now()),
  (gen_random_uuid(), 'ec6dc1bb-5376-49ee-b23a-040b45672656', 'GraphQL', 'graphql', 'GraphQL schema, resolvers, Apollo, queries, mutations và subscriptions.', 11, true, now(), now()),
  (gen_random_uuid(), 'ec6dc1bb-5376-49ee-b23a-040b45672656', 'Web Security', 'web-security', 'OWASP, XSS, CSRF, SQL injection, HTTPS, CORS và secure coding practices.', 12, true, now(), now()),
  (gen_random_uuid(), 'ec6dc1bb-5376-49ee-b23a-040b45672656', 'Performance Optimization', 'web-performance', 'Web vitals, lazy loading, code splitting, caching strategies và optimization.', 13, true, now(), now()),
  (gen_random_uuid(), 'ec6dc1bb-5376-49ee-b23a-040b45672656', 'Testing', 'web-testing', 'Jest, Cypress, unit testing, integration testing và TDD.', 14, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 13. Phát triển ứng dụng di động (746f32a1-b863-47b3-a384-4908ee67d89a) - sub của Phát triển
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), '746f32a1-b863-47b3-a384-4908ee67d89a', 'React Native', 'react-native', 'Xây dựng app iOS/Android với React Native, Expo, navigation và native modules.', 1, true, now(), now()),
  (gen_random_uuid(), '746f32a1-b863-47b3-a384-4908ee67d89a', 'Flutter', 'flutter', 'Cross-platform app với Flutter, Dart, widgets và responsive UI.', 2, true, now(), now()),
  (gen_random_uuid(), '746f32a1-b863-47b3-a384-4908ee67d89a', 'iOS (Swift)', 'ios-swift', 'Native iOS development với Swift, SwiftUI, UIKit và App Store deployment.', 3, true, now(), now()),
  (gen_random_uuid(), '746f32a1-b863-47b3-a384-4908ee67d89a', 'Android (Kotlin)', 'android-kotlin', 'Native Android development với Kotlin, Jetpack Compose và Google Play.', 4, true, now(), now()),
  (gen_random_uuid(), '746f32a1-b863-47b3-a384-4908ee67d89a', 'PWA', 'pwa', 'Progressive Web Apps, service workers, offline support và web app manifest.', 5, true, now(), now()),
  (gen_random_uuid(), '746f32a1-b863-47b3-a384-4908ee67d89a', 'App Architecture', 'app-architecture', 'Clean Architecture, MVVM, state management, dependency injection và best practices.', 6, true, now(), now()),
  (gen_random_uuid(), '746f32a1-b863-47b3-a384-4908ee67d89a', 'Push Notifications', 'push-notifications', 'Firebase Cloud Messaging, OneSignal và notification strategies.', 7, true, now(), now()),
  (gen_random_uuid(), '746f32a1-b863-47b3-a384-4908ee67d89a', 'App Store Optimization', 'app-store-optimization', 'ASO, keywords, screenshots, reviews và tăng visibility trên stores.', 8, true, now(), now()),
  (gen_random_uuid(), '746f32a1-b863-47b3-a384-4908ee67d89a', 'Analytics & Crashlytics', 'analytics-crashlytics', 'Firebase Analytics, crash reporting, performance monitoring và user tracking.', 9, true, now(), now()),
  (gen_random_uuid(), '746f32a1-b863-47b3-a384-4908ee67d89a', 'In-app Purchases', 'in-app-purchases', 'Subscription, one-time purchase, Stripe, RevenueCat và monetization strategies.', 10, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 14. Ngôn ngữ lập trình (cff5f5a2-0cab-465f-8845-003a9354c21a) - sub của Phát triển
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), 'cff5f5a2-0cab-465f-8845-003a9354c21a', 'Python', 'python', 'Python programming: syntax, OOP, data structures, libraries và ứng dụng đa dạng.', 1, true, now(), now()),
  (gen_random_uuid(), 'cff5f5a2-0cab-465f-8845-003a9354c21a', 'Java', 'java', 'Java SE/EE, OOP, Spring Framework, JVM và enterprise development.', 2, true, now(), now()),
  (gen_random_uuid(), 'cff5f5a2-0cab-465f-8845-003a9354c21a', 'C#', 'c-sharp', 'C# programming, .NET, ASP.NET, Unity game development và Windows apps.', 3, true, now(), now()),
  (gen_random_uuid(), 'cff5f5a2-0cab-465f-8845-003a9354c21a', 'Go', 'go', 'Go (Golang) programming, concurrency, microservices và cloud-native development.', 4, true, now(), now()),
  (gen_random_uuid(), 'cff5f5a2-0cab-465f-8845-003a9354c21a', 'Rust', 'rust', 'Rust programming, memory safety, ownership system và system programming.', 5, true, now(), now()),
  (gen_random_uuid(), 'cff5f5a2-0cab-465f-8845-003a9354c21a', 'Ruby', 'ruby', 'Ruby programming, Ruby on Rails, metaprogramming và web development.', 6, true, now(), now()),
  (gen_random_uuid(), 'cff5f5a2-0cab-465f-8845-003a9354c21a', 'Swift', 'swift', 'Swift programming language, iOS/macOS development và Swift ecosystem.', 7, true, now(), now()),
  (gen_random_uuid(), 'cff5f5a2-0cab-465f-8845-003a9354c21a', 'Kotlin', 'kotlin', 'Kotlin programming, Android development, coroutines và null safety.', 8, true, now(), now()),
  (gen_random_uuid(), 'cff5f5a2-0cab-465f-8845-003a9354c21a', 'Scala', 'scala', 'Scala programming, functional programming, Spark và big data processing.', 9, true, now(), now()),
  (gen_random_uuid(), 'cff5f5a2-0cab-465f-8845-003a9354c21a', 'Dart', 'dart', 'Dart programming, Flutter framework và cross-platform development.', 10, true, now(), now()),
  (gen_random_uuid(), 'cff5f5a2-0cab-465f-8845-003a9354c21a', 'PHP', 'php', 'PHP 8, Laravel, WordPress plugins, Composer và web development.', 11, true, now(), now()),
  (gen_random_uuid(), 'cff5f5a2-0cab-465f-8845-003a9354c21a', 'R', 'r', 'R programming, data analysis, statistics, ggplot2 và data science.', 12, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 15. C++ (788fc821-01eb-464f-b24d-5355ab3a5045) - sub của Ngôn ngữ lập trình
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), '788fc821-01eb-464f-b24d-5355ab3a5045', 'C++ Cơ bản', 'c-co-ban', 'C++ fundamentals: syntax, variables, loops, functions, pointers và memory basics.', 1, true, now(), now()),
  (gen_random_uuid(), '788fc821-01eb-464f-b24d-5355ab3a5045', 'OOP với C++', 'oop-voi-cpp', 'Object-Oriented Programming: classes, inheritance, polymorphism và encapsulation.', 2, true, now(), now()),
  (gen_random_uuid(), '788fc821-01eb-464f-b24d-5355ab3a5045', 'STL & Containers', 'stl-containers', 'Standard Template Library: vector, map, set, algorithms và iterators.', 3, true, now(), now()),
  (gen_random_uuid(), '788fc821-01eb-464f-b24d-5355ab3a5045', 'C++ Hiện đại (C++11/14/17/20)', 'cpp-hien-dai', 'Modern C++ features: smart pointers, lambda, move semantics, ranges và concepts.', 4, true, now(), now()),
  (gen_random_uuid(), '788fc821-01eb-464f-b24d-5355ab3a5045', 'Game Development với C++', 'game-dev-cpp', 'Phát triển game với C++, Unreal Engine, DirectX/OpenGL và game loops.', 5, true, now(), now()),
  (gen_random_uuid(), '788fc821-01eb-464f-b24d-5355ab3a5045', 'System Programming', 'system-programming', 'Low-level programming, OS concepts, file I/O và system calls.', 6, true, now(), now()),
  (gen_random_uuid(), '788fc821-01eb-464f-b24d-5355ab3a5045', 'Data Structures & Algorithms', 'ds-algo-cpp', 'Cấu trúc dữ liệu và giải thuật với C++, competitive programming.', 7, true, now(), now()),
  (gen_random_uuid(), '788fc821-01eb-464f-b24d-5355ab3a5045', 'Multithreading', 'multithreading-cpp', 'Concurrency, threads, mutex, async programming và parallel processing.', 8, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 16. Guitar (d895086c-4b31-419f-9644-d99982622037) - sub của Âm nhạc
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), 'd895086c-4b31-419f-9644-d99982622037', 'Guitar điện', 'guitar-dien', 'Electric guitar: amplifiers, effects, techniques và các phong cách rock, metal, blues.', 1, true, now(), now()),
  (gen_random_uuid(), 'd895086c-4b31-419f-9644-d99982622037', 'Guitar acoustic', 'guitar-acoustic', 'Acoustic guitar: fingerpicking, strumming, singer-songwriter và folk style.', 2, true, now(), now()),
  (gen_random_uuid(), 'd895086c-4b31-419f-9644-d99982622037', 'Classical Guitar', 'classical-guitar', 'Guitar cổ điển: classical technique, nylon strings, baroque và classical repertoire.', 3, true, now(), now()),
  (gen_random_uuid(), 'd895086c-4b31-419f-9644-d99982622037', 'Jazz Guitar', 'jazz-guitar', 'Guitar jazz: chords, comping, improvisation và jazz standards.', 4, true, now(), now()),
  (gen_random_uuid(), 'd895086c-4b31-419f-9644-d99982622037', 'Fingerstyle', 'fingerstyle', 'Fingerstyle guitar: arrangement, Travis picking, percussive techniques.', 5, true, now(), now()),
  (gen_random_uuid(), 'd895086c-4b31-419f-9644-d99982622037', 'Blues Guitar', 'blues-guitar', 'Guitar blues: blues scale, bends, vibrato, turnarounds và blues progression.', 6, true, now(), now()),
  (gen_random_uuid(), 'd895086c-4b31-419f-9644-d99982622037', 'Music Theory cho Guitar', 'music-theory-guitar', 'Lý thuyết âm nhạc áp dụng cho guitar: scales, modes, chord construction.', 7, true, now(), now()),
  (gen_random_uuid(), 'd895086c-4b31-419f-9644-d99982622037', 'Recording Guitar', 'recording-guitar', 'Thu âm guitar: microphone placement, DI, amp modeling và production.', 8, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 17. Excel (e2d3d1e5-6c58-4582-8aeb-cbfad3c53c67) - sub của Tài chính và kế toán
-- ============================================================
INSERT INTO public.topics (id, category_id, name, slug, description, order_index, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), 'e2d3d1e5-6c58-4582-8aeb-cbfad3c53c67', 'Excel Cơ bản', 'excel-co-ban', 'Excel fundamentals: cells, formulas, basic functions, formatting và data entry.', 1, true, now(), now()),
  (gen_random_uuid(), 'e2d3d1e5-6c58-4582-8aeb-cbfad3c53c67', 'Excel Nâng cao', 'excel-nang-cao', 'Advanced Excel: complex formulas, nested functions, array formulas và advanced features.', 2, true, now(), now()),
  (gen_random_uuid(), 'e2d3d1e5-6c58-4582-8aeb-cbfad3c53c67', 'Pivot Table', 'pivot-table', 'Pivot Table: grouping, filtering, calculated fields, slicers và pivot charts.', 3, true, now(), now()),
  (gen_random_uuid(), 'e2d3d1e5-6c58-4582-8aeb-cbfad3c53c67', 'Power Query', 'power-query', 'Power Query: data transformation, ETL, merging queries và automation.', 4, true, now(), now()),
  (gen_random_uuid(), 'e2d3d1e5-6c58-4582-8aeb-cbfad3c53c67', 'Power Pivot & DAX', 'power-pivot-dax', 'Power Pivot, DAX formulas, data modeling và analysis với large datasets.', 5, true, now(), now()),
  (gen_random_uuid(), 'e2d3d1e5-6c58-4582-8aeb-cbfad3c53c67', 'VBA & Macros', 'vba-macros', 'Excel VBA programming, macros, automation và user-defined functions.', 6, true, now(), now()),
  (gen_random_uuid(), 'e2d3d1e5-6c58-4582-8aeb-cbfad3c53c67', 'Data Visualization', 'excel-data-visualization', 'Charts, graphs, conditional formatting, sparklines và dashboard design.', 7, true, now(), now()),
  (gen_random_uuid(), 'e2d3d1e5-6c58-4582-8aeb-cbfad3c53c67', 'Financial Modeling', 'financial-modeling-excel', 'Financial modeling trong Excel: DCF, sensitivity analysis và 3-statement models.', 8, true, now(), now()),
  (gen_random_uuid(), 'e2d3d1e5-6c58-4582-8aeb-cbfad3c53c67', 'Excel cho Kế toán', 'excel-ke-toan', 'Ứng dụng Excel trong kế toán: ledger, trial balance, financial statements.', 9, true, now(), now()),
  (gen_random_uuid(), 'e2d3d1e5-6c58-4582-8aeb-cbfad3c53c67', 'Keyboard Shortcuts', 'excel-shortcuts', 'Excel keyboard shortcuts để tăng tốc độ làm việc và productivity.', 10, true, now(), now())
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- Verify: đếm số topics mỗi category
-- ============================================================
-- SELECT c.name, COUNT(t.id) as topic_count
-- FROM categories c
-- LEFT JOIN topics t ON t.category_id = c.id
-- GROUP BY c.id, c.name
-- ORDER BY c.name;
